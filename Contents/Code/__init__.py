PREFIX = '/video/spike'
TITLE = 'Spike'
ART = 'art-default.jpg'
ICON = 'icon-default.jpg'
BASE_URL = 'http://www.spike.com'

# Pull the json from the HTML content to prevent any issues with redirects and/or bad urls
RE_MANIFEST_URL = Regex('var triforceManifestURL = "(.+?)";', Regex.DOTALL)
RE_MANIFEST = Regex('var triforceManifestFeed = (.+?);', Regex.DOTALL)

EXCLUSIONS = []
SEARCH ='http://relaunch-search.spike.com/solr/spike/select?q=%s&wt=json&defType=edismax&start='
SEARCH_TYPE = ['Video', 'Episode', 'Series']
ENT_LIST = ['ent_m100', 'ent_m069', 'ent_m150', 'ent_m151', 'ent_m112', 'ent_m116']

####################################################################################################
def Start():

    ObjectContainer.title1 = 'Spike'
    HTTP.CacheTime = CACHE_1HOUR
    HTTP.Headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'

####################################################################################################
@handler(PREFIX, TITLE, art=ART, thumb=ICON)
def MainMenu():

    oc = ObjectContainer()
    oc.add(DirectoryObject(key = Callback(FeedMenu, title="Full Episodes", url=BASE_URL+'/full-episodes'), title = "Full Episodes"))
    oc.add(DirectoryObject(key = Callback(FeedMenu, title="Shows", url=BASE_URL+'/shows'), title = "Shows"))
    oc.add(InputDirectoryObject(key = Callback(SearchSections, title="Search"), title = "Search"))

    return oc

####################################################################################################
# This function pulls the json feeds in the ENT_LIST for any page
@route(PREFIX + '/feedmenu')
def FeedMenu(title, url, thumb=''):
    
    oc = ObjectContainer(title2=title)
    feed_title = title
    try:
        content = HTTP.Request(url, cacheTime=CACHE_1DAY).content
        try: 
            zone_list = JSON.ObjectFromString(RE_MANIFEST.search(content).group(1))['manifest']['zones']
        except: 
            zone_list = JSON.ObjectFromURL(RE_MANIFEST_URL.search(content).group(1))['manifest']['zones']
    except:
        return ObjectContainer(header="Incompatible", message="Unable to find video feeds for %s." % (url))

    if not thumb:
        try: thumb = HTML.ElementFromString(content).xpath('//meta[@property="og:image"]/@content')[0].strip()
        except: thumb = ''

    for zone in zone_list:

        if zone in ('header', 'footer', 'ads-reporting', 'ENT_M171'):
            continue

        json_feed = zone_list[zone]['feed']

        # Split feed to get ent code
        try: ent_code = json_feed.split('/feeds/')[1].split('/')[0]
        except:  ent_code = ''

        ent_code = ent_code.split('_spike')[0]

        if ent_code not in ENT_LIST:
            continue

        json = JSON.ObjectFromURL(json_feed, cacheTime = CACHE_1DAY)

        # Create a menu for the main full episodes feed (ent_m151) for all videos and for each show
        if ent_code=='ent_m151':
            try: title = json['result']['promo']['headline'].title()
            except: title = feed_title
            oc.add(DirectoryObject(key=Callback(ShowVideos, title=title, url=json_feed),
                title=title,
                thumb=Resource.ContentsOfURLWithFallback(url=thumb)
            ))
            for item in json['result']['shows']:
                oc.add(DirectoryObject(key=Callback(ShowVideos, title=item['title'], url=item['url']),
                    title=item['title']
                ))
        
        # Create menu for each show's full episodes feed (ent_m112)
        elif ent_code == 'ent_m112':
            try: title = json['result']['promo']['headline'].title()
            except: title = feed_title
            oc.add(DirectoryObject(
                key = Callback(ShowVideos, title=title, url=json_feed),
                title = title,
                thumb = Resource.ContentsOfURLWithFallback(url=thumb)
            ))

        # Create menu items for other feeds to go to Produce Sections
        # ent_m100-featured show, ent_m150-shows atoz, ent_m069-all shows and ent_m116 - each show's video clips
        else:
            if ent_code == 'ent_m116':
                # Video clip feeds for each show (ent_m116) results are under filters and the title is under promo/headline
                result_type = 'filters'
                try: title = json['result']['promo']['headline'].title()
                except: title = feed_title
            else:
                # All show feed results are under data/items (ent_m100, ent_m150, and ent_m069)
                result_type = 'items'
                # The title for most show feeds (ent_m100, ent_m150) are under data/headerText
                try: title = json['result']['data']['headerText'].title()
                except:
                    # The title for Spike all shows (ent_m069) is under data/header/title
                    try: title = json['result']['data']['header']['title'].title()
                    except: title = feed_title
            oc.add(DirectoryObject(key=Callback(ProduceSection, title=title, url=json_feed, result_type=result_type),
                title=title,
                thumb=Resource.ContentsOfURLWithFallback(url=thumb)
            ))
            
    if len(oc) < 1:
        return ObjectContainer(header="Empty", message="There are no results to list.")
    else:
        return oc
####################################################################################################
# This function produces sections from a json feeds including shows(ent_m100 and ent_m069), AtoZ shows(ent_m150), and video filters(ent_m116)
# Spike uses ent_069 for all shows, but we are keeping the alpha code in case it is added later
@route(PREFIX + '/producesection', alpha=int)
def ProduceSection(title, url, result_type, thumb='', alpha=None):

    oc = ObjectContainer(title2=title)
    (section_title, feed_url) = (title, url)
    counter=0
    json = JSON.ObjectFromURL(url)

    # Create lists
    try: 
        # Create list for show feeds (data items)
        item_list = json['result']['data'][result_type]
    except: 
        # Create list for video feed filters
        try: item_list = json['result'][result_type]
        except: item_list = []
    # Create list for alphabet sections for the AtoZ show feeds
    if '/ent_m150/' in feed_url and alpha:
        item_list = json['result']['data']['items'][alpha]['sortedItems']
    for item in item_list:
        # Produce menu items for show lists
        if '/ent_m150/' in feed_url or '/ent_m100/' in feed_url or '/ent_m069/' in feed_url:
            # Produce alphabetic menu items for AtoZ
            if '/ent_m150/' in feed_url and not alpha:
                oc.add(DirectoryObject(
                    key=Callback(ProduceSection, title=item['letter'], url=feed_url, result_type=result_type, alpha=counter),
                    title=item['letter']
                ))
                counter=counter+1
            # Produce menu items for each show (under Featured, a letter, etc)
            else:
                try: url = item['canonicalURL']
                except:
                    try: url = item['url']
                    except: continue
                # Skip bad show urls that do not include '/shows/' or events. If '/events/' there is no manifest.
                if '/shows/' not in url:
                    continue
                if item['title'] in EXCLUSIONS:
                    continue
                try: thumb = item['image']['url']
                except: 
                    try: thumb = item['image'][0]['url']
                    except: thumb = thumb
                if thumb.startswith('//'):
                    thumb = 'https:' + thumb
                oc.add(DirectoryObject(
                    key=Callback(FeedMenu, title=item['title'], url=url, thumb=thumb),
                    title=item['title'],
                    thumb = Resource.ContentsOfURLWithFallback(url=thumb)
                ))

        # Produce menu items for video filters for the video clips for an individual a show
        else:
            # Skip any empty sections
            count=item['count']
            if  count==0:
                continue
            oc.add(DirectoryObject(
                key=Callback(ShowVideos, title=item['name'], url=item['url']),
                title=item['name'],
                thumb=Resource.ContentsOfURLWithFallback(url=thumb)
            ))
    
    if len(oc) < 1:
        Log ('still no value for objects')
        return ObjectContainer(header="Empty", message="There are no results to list right now.")
    else:
        return oc
#######################################################################################
# This function produces the videos listed in a json feed under items
@route(PREFIX + '/showvideos')
def ShowVideos(title, url):

    oc = ObjectContainer(title2=title)
    json = JSON.ObjectFromURL(url)
    # Currently all video results are under result/items but added result/data/items in case the feeds change
    try: videos = json['result']['items']
    except:
        try: videos = json['result']['data']['items']
        except: return ObjectContainer(header="Empty", message="There are no videos to list right now.")
    
    for video in videos:

        vid_url = video['canonicalURL']

        # catch any bad links that get sent here
        if not ('/video-clips/') in vid_url and not ('/video-playlists/') in vid_url and not ('/full-episodes/') in vid_url and not ('/episodes/') in vid_url:
            continue
        if 'bellator.spike.com' in vid_url:
            continue

        # Individual show images are under images and full episode feeds are under image
        try: thumb = video['images'][0]['url']
        except:
            try: thumb = video['image'][0]['url']
            except:  thumb = None
        if thumb and thumb.startswith('//'):
            thumb = 'http:' + thumb

        # Show names for Individual shows are under show/title and full episode feeds are under showTitle
        try: show = video['show']['title']
        except: show = video['showTitle']
        try: episode = int(video['season']['episodeNumber'])
        except: episode = 0
        try: season = int(video['season']['seasonNumber'])
        except: season = 0
        
        # Dates for Individual shows are unix and full episode feeds are strings
        try: raw_date = video['airDate']
        except: raw_date = video['publishDate']
        if raw_date and raw_date.isdigit(): 
            raw_date = Datetime.FromTimestamp(float(raw_date)).strftime('%m/%d/%Y')
        date = Datetime.ParseDate(raw_date)

        # Duration for Individual shows are integers/floats and full episode feeds are strings
        duration = video['duration']
        if duration:
            if isinstance(duration, int):
                duration = duration * 1000
            else:
                try: duration = Datetime.MillisecondsFromString(duration)
                except:
                    # Durations for clips have decimal points
                    try: duration = int(duration.split('.')[0]) * 1000
                    except:  duration = 0

        # Everything else has episode and show info now
        oc.add(EpisodeObject(
            url = vid_url, 
            show = show,
            season = season,
            index = episode,
            title = video['title'], 
            thumb = Resource.ContentsOfURLWithFallback(url=thumb ),
            originally_available_at = date,
            duration = duration,
            summary = video['description']
        ))

    try: next_page = json['result']['nextPageURL']
    except: next_page = None

    if next_page and len(oc) > 0:

        oc.add(NextPageObject(
            key = Callback(ShowVideos, title=title, url=next_page),
            title = 'Next Page ...'
        ))

    if len(oc) < 1:
        Log ('still no value for objects')
        return ObjectContainer(header="Empty", message="There are no unlocked videos available to watch.")
    else:
        return oc
####################################################################################################
# This function produces the types of results (show, video, etc) returned from a search
@route(PREFIX + '/searchsections')
def SearchSections(title, query):
    
    oc = ObjectContainer(title2=title)
    json_url = SEARCH %String.Quote(query, usePlus = False)
    local_url = json_url + '0&facet=on&facet.field=bucketName_s'
    json = JSON.ObjectFromURL(local_url)
    i = 0
    search_list = json['facet_counts']['facet_fields']['bucketName_s']
    for item in search_list:
        if item in SEARCH_TYPE and search_list[i+1]!=0:
            oc.add(DirectoryObject(key = Callback(Search, title=item, url=json_url, search_type=item), title = item))
        i=i+1

    return oc
####################################################################################################
# This function produces the results for a search under each search type
@route(PREFIX + '/search', start=int)
def Search(title, url, start=0, search_type=''):

    oc = ObjectContainer(title2=title)
    local_url = '%s%s&fq=bucketName_s:%s' %(url, start, search_type)
    json = JSON.ObjectFromURL(local_url)

    for item in json['response']['docs']:

        result_type = item['bucketName_s']
        title = item['title_t']
        full_title = '%s: %s' % (result_type, title)

        try: item_url = item['url_s']
        except: continue
        # Skip bellator url that are not part of the URL service
        if not item_url.startswith(BASE_URL):
            continue

        # For Shows
        if result_type == 'Series':

            oc.add(DirectoryObject(
                key = Callback(FeedMenu, title=item['title_t'], url=item_url, thumb=item['imageUrl_s']),
                title = full_title,
                thumb = Resource.ContentsOfURLWithFallback(url=item['imageUrl_s'])
            ))

        # For Episodes and ShowVideo(video clips)
        else:
            try: season = int(item['seasonNumber_s'].split(':')[0])
            except: season = None

            try: episode = int(item['episodeNumber_s'])
            except: episode = None

            try: show = item['seriesTitle_t']
            except: show = None

            try: summary = item['description_t']
            except: summary = None

            try: duration = Datetime.MillisecondsFromString(item['duration_s'])
            except: duration = None

            oc.add(EpisodeObject(
                url = item_url, 
                show = show, 
                title = full_title, 
                thumb = Resource.ContentsOfURLWithFallback(url=item['imageUrl_s']),
                summary = summary, 
                season = season, 
                index = episode, 
                duration = duration, 
                originally_available_at = Datetime.ParseDate(item['contentDate_dt'])
            ))

    if json['response']['start']+10 < json['response']['numFound']:

        oc.add(NextPageObject(
            key = Callback(Search, title='Search', url=url, search_type=search_type, start=start+10),
            title = 'Next Page ...'
        ))

    if len(oc) < 1:
        return ObjectContainer(header="Empty", message="There are no results to list.")
    else:
        return oc
