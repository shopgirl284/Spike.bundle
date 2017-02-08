PREFIX = '/video/spike'
TITLE = 'Spike'
BASE_URL = 'http://www.spike.com'

# Pull the json from the HTML content to prevent any issues with redirects and/or bad urls
RE_MANIFEST = Regex('var triforceManifestFeed = (.+?);', Regex.DOTALL)

EXCLUSIONS = []
ENT_LIST = ['ent_m100', 'ent_m069', 'ent_m150', 'ent_m151', 'ent_m112', 'ent_m116']
####################################################################################################
def Start():

    ObjectContainer.title1 = 'Spike'
    HTTP.CacheTime = CACHE_1HOUR
    HTTP.Headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'

####################################################################################################
@handler(PREFIX, TITLE)
def MainMenu():

    oc = ObjectContainer()
    oc.add(DirectoryObject(key = Callback(FeedMenu, title="Full Episodes", url=BASE_URL+'/full-episodes'), title = "Full Episodes"))
    oc.add(DirectoryObject(key = Callback(FeedMenu, title="Shows", url=BASE_URL+'/shows'), title = "Shows"))

    return oc

####################################################################################################
# This function pulls the various json feeds for video sections of a page 
@route(PREFIX + '/feedmenu')
def FeedMenu(title, url, thumb=''):
    
    oc = ObjectContainer(title2=title)
    feed_title = title
    try:
        content = HTTP.Request(url, cacheTime=CACHE_1DAY).content
        zone_list = JSON.ObjectFromString(RE_MANIFEST.search(content).group(1))['manifest']['zones']
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

        #Log('the value of ent_code is %s' %ent_code)
        ent_code = ent_code.split('_spike')[0]

        if ent_code not in ENT_LIST:
            continue

        json = JSON.ObjectFromURL(json_feed, cacheTime = CACHE_1DAY)

        try: title = json['result']['promo']['headline'].title()
        except: 
            # Using ent_m069 code for All shows and those shows are in a data item
            try: title = json['result']['data']['header']['title'].title()
            except: title = feed_title
        # Create menu for the ent_m151 - full episodes to produce videos and menu items for full episode feeds by show
        if ent_code=='ent_m151':
            oc.add(DirectoryObject(key=Callback(ShowVideos, title=title, url=json_feed),
                title=title,
                thumb=Resource.ContentsOfURLWithFallback(url=thumb)
            ))
            for item in json['result']['shows']:
                oc.add(DirectoryObject(key=Callback(ShowVideos, title=item['title'], url=item['url']),
                    title=item['title']
                ))
        # Create menu for each show's full episodes - ent_m112
        elif ent_code == 'ent_m112':

            oc.add(DirectoryObject(
                key = Callback(ShowVideos, title=title, url=json_feed),
                title = title,
                thumb = Resource.ContentsOfURLWithFallback(url=thumb)
            ))

        # Create menu items for those that need to go to Produce Sections
        # ent_m100-featured show and ent_m150-all shows and ent_m112 - video clips by season
        # ent_m100 and ent_m150 are result type shows and ent_m116 result type filters
        else:
            if ent_code == 'ent_m116':
                result_type = 'filters'
            else:
                result_type = 'shows'
            oc.add(DirectoryObject(key=Callback(ProduceSection, title=title, url=json_feed, result_type=result_type),
                title=title,
                thumb=Resource.ContentsOfURLWithFallback(url=thumb)
            ))
            
    if len(oc) < 1:
        return ObjectContainer(header="Empty", message="There are no results to list.")
    else:
        return oc
#####################################################################################
# For Producing the sections from various json feeds
# This function can produce show lists, AtoZ show lists, and video filter lists
# Even though Spike uses ent_069 for all shows, we are keeping the alpha code since it may be added later
@route(PREFIX + '/producesections')
def ProduceSection(title, url, result_type, thumb='', alpha=''):
    
    oc = ObjectContainer(title2=title)
    (section_title, feed_url) = (title, url)
    json = JSON.ObjectFromURL(url)

    # Using ent_mo69 for all shows right now and they are listed as data items
    if '/feeds/ent_m069' in feed_url:
        item_list = json['result']['data']['items']
    else:
        item_list = json['result'][result_type]
    #item_list = json['result'][result_type]
    # Create item list for individual sections of alphabet for the All listings
    if '/feeds/ent_m150' in feed_url and alpha:
        item_list = json['result'][result_type][alpha]
    for item in item_list:
        # Create a list of show sections
        if result_type=='shows':
            if '/feeds/ent_m150' in feed_url and not alpha:
                oc.add(DirectoryObject(
                    key=Callback(ProduceSection, title=item, url=feed_url, result_type=result_type, alpha=item),
                    title=item.replace('hash', '#').title()
                ))
            else:
                if item['title'] in EXCLUSIONS:
                    continue
                try: url = item['url']
                except: url = item['canonicalURL']
                # Skip bad show urls that do not include '/shows/' or events. If '/events/' there is no manifest.
                if '/shows/' not in url:
                    continue
                try: thumb = item['images'][0]['url']
                except: 
                    item['image'][0]['url']
                    thumb = thumb
                oc.add(DirectoryObject(
                    key=Callback(FeedMenu, title=item['title'], url=url, thumb=thumb),
                    title=item['title'],
                    thumb = Resource.ContentsOfURLWithFallback(url=thumb)
                ))

        # Create season sections for filters
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
# This function produces the videos listed in json feed under items
@route(PREFIX + '/showvideos')
def ShowVideos(title, url):

    oc = ObjectContainer(title2=title)
    json = JSON.ObjectFromURL(url)
    #try: videos = json['result']['items']
    #except: return ObjectContainer(header="Empty", message="There are no videos to list right now.")
    try: videos = json['result']['items']
    except:
        try: videos = json['result']['data']['items']
        except: return ObjectContainer(header="Empty", message="There are no videos to list right now.")
    
    for video in videos:

        vid_url = video['canonicalURL']

        # catch any bad links that get sent here
        if not ('/video-clips/') in vid_url and not ('/video-playlists/') in vid_url and not ('/full-episodes/') in vid_url:
            continue
        if 'bellator.spike.com' in vid_url:
            continue

        thumb = video['images'][0]['url']

        show = video['show']['title']
        try: episode = int(video['season']['episodeNumber'])
        except: episode = 0
        try: season = int(video['season']['seasonNumber'])
        except: season = 0
        
        try: unix_date = video['airDate']
        except:
            try: unix_date = video['publishDate']
            except: unix_date = unix_date = video['date']['originalPublishDate']['timestamp']
        date = Datetime.FromTimestamp(float(unix_date)).strftime('%m/%d/%Y')
        date = Datetime.ParseDate(date)

        # Durations for clips have decimal points
        duration = video['duration']
        if not isinstance(duration, int):
            duration = int(duration.split('.')[0])
        duration = duration * 1000

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
