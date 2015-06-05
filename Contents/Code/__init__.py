BASE_URL = 'http://www.spike.com'
SHOW_URL = 'http://www.spike.com/shows'

RE_JSON = Regex('var triforceManifestFeed = (.+?)};', Regex.DOTALL)
JSON_MENU = 'http://www.spike.com/modules/ent_m066_spike/3.1.1/85ba7bc8-b78f-4158-89f1-84636b555f64'

# All Access E3('/shows/32') shows no videos because it has not been updated to the new format
SHOW_EXCLUSIONS = ["All Access: E3"]

####################################################################################################
def Start():

    ObjectContainer.title1 = 'Spike'
    HTTP.CacheTime = CACHE_1HOUR
    HTTP.Headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'

####################################################################################################
@handler("/video/spike", "Spike")
def MainMenu():

    oc = ObjectContainer()
    oc.add(DirectoryObject(key=Callback(ShowList, title='Shows', list_type=0), title='Shows')) 
    oc.add(DirectoryObject(key=Callback(ShowList, title='Full Episodes', list_type=1), title='Full Episodes')) 
    oc.add(DirectoryObject(key=Callback(AllMenu, title='All Shows'), title='All Shows'))

    return oc

####################################################################################################
# This function produces a list from the menu json of shows or shows with full episodes
@route("/video/spike/showlist", list_type=int)
def ShowList(title, list_type=0):

    oc = ObjectContainer(title2 = title)

    try: json = JSON.ObjectFromURL(JSON_MENU) 
    except: json = None

    if json: 

        for show in json['result']['siteNavigation'][list_type]['entries']:

            show_url = show['url']

            if not show_url.startswith('http:'):
                show_url = BASE_URL + show_url

            show_title = show['title']

            # Send shows to sections and full episodes straight to JSONVideoBrowser
            if list_type == 0:
                oc.add(DirectoryObject(key=Callback(Sections, url=show_url, title=show_title), title=show_title))
            else:
                # To prevent multiple http request when producing full episode shows
                # send them to JSONVideoBrowser and let the feed be pulled there
                oc.add(DirectoryObject(key=Callback(JSONVideoBrowser, url=show_url, title=show_title), title=show_title))

    if len(oc) < 1:
        return ObjectContainer(header="Spike", message="There are no shows to list.")
    else:
        return oc

####################################################################################################
# This function produces a list of all shows from the /shows page
@route("/video/spike/allmenu")
def AllMenu(title):

    oc = ObjectContainer(title2=title)
    data = HTML.ElementFromURL(SHOW_URL)

    # Shows are pulled from the main show page and this pulls shows from all four sections listed
    for shows in data.xpath('//div[@class="middle"]/div/ul/li/a'):

        show_title = shows.text.strip()

        if show_title in SHOW_EXCLUSIONS:
            continue

        url = shows.get('href')

        if not url.startswith('http://'):
            url = '%s/%s' % (BASE_URL, url.lstrip('/'))

        # Send specials to separate function to find videos
        if '/shows/' in url:
            oc.add(DirectoryObject(key=Callback(Sections, url=url, title=show_title), title=show_title))
        else:
            oc.add(DirectoryObject(key=Callback(SpecialSections, url=url, title=show_title), title=show_title))

    oc.objects.sort(key = lambda obj: obj.title)

    if len(oc) < 1:
        return ObjectContainer(header="Spike", message="There are no shows to list.")
    else:
        return oc

####################################################################################################
# This function decides whether the show has full episodes and/or video clips
@route("/video/spike/sections")
def Sections(title, url):

    oc = ObjectContainer(title2=title)

    try:
        content = HTTP.Request(url, cacheTime=CACHE_1DAY).content
        html = HTML.ElementFromString(content)
    except:
        return ObjectContainer(header="Spike", message="This show does not have a url.")

    try:
        # A few will not pick up json without looking for '};' at end
        json_data = RE_JSON.search(content).group(1) + '}'
        json = JSON.ObjectFromString(json_data)
    except: json = None

    if json:

        show_sections = html.xpath('//div[@id="t4_lc"]/div')

        for sections in show_sections:

            sec_id = sections.xpath('./@id')[0]
            feed_url = json['manifest']['zones'][sec_id]['feed']

            try: sec_json = JSON.ObjectFromURL(feed_url, cacheTime=CACHE_1DAY) 
            except: sec_json = None

            if sec_json:

                sec_title = sec_json['result']['promo']['headline']

                # found a few that are empty but do not have a section title
                if not sec_title:
                    continue

                # some will create a section even if it is empty
                try: sec_items = sec_json['result']['items'][0]
                except: continue

                # Send video clips to be broken into seasons
                if sec_title=='Video Clips':
                    oc.add(DirectoryObject(key=Callback(SeasonFilters, url=feed_url, title=sec_title), title=sec_title))
                else:
                    oc.add(DirectoryObject(key=Callback(JSONVideoBrowser, url=feed_url, title=sec_title), title=sec_title))

    else:
        Log('no json')
        return ObjectContainer(header="Spike", message="There are no compatible videos available.")

    if len(oc) < 1:
        return ObjectContainer(header="Spike", message="There are no videos available.")
    else:
        return oc

####################################################################################################
# This function splits video clips into seasons
# There is no point splitting full episodes into seasons because most listed are highlights
# which are not supported by the URL service
@route("/video/spike/seasonfilters")
def SeasonFilters(title, url):

    oc = ObjectContainer(title2 = title)

    try: json = JSON.ObjectFromURL(url, cacheTime=CACHE_1DAY) 
    except: json= None

    if json: 

        for filter in json['result']['filters']:

            filter_url = filter['url']
            filter_title = filter['name']
            oc.add(DirectoryObject(key=Callback(JSONVideoBrowser, url=filter_url, title=filter_title), title=filter_title))

    if len(oc) < 1:
        return ObjectContainer(header="Spike", message="There are no compatible videos available." )
    else:
        return oc

####################################################################################################
# This function pulls the videos from a json feed
@route("/video/spike/jsonvideobrowser")
def JSONVideoBrowser(url, title):

    oc = ObjectContainer(title2 = title)

    # Full episode section would have to do too many http requests 
    # if we pull the feed url when we pull the show names so we do it here
    if url.endswith('/full-episodes'): 
        feed_type = 't4_lc_promo2'
        url = JSONFeed(url, feed_type)

    try: json = JSON.ObjectFromURL(url) 
    except: json= None

    if json: 

        try: multi_vids = json['result']['items'][0]
        except: multi_vids = None

        # This handles json for a single episode json
        # This is used by specials that have a full show link
        if not multi_vids:

            # Check to see if json contains any results otherwise send error
            try: locked = json['result']['episode']['distPolicy']['authTve']
            except: return ObjectContainer(header="Spike", message="There are currently no videos available.")

            available = json['result']['episode']['distPolicy']['available']
            duration = json['result']['episode']['duration']

            try: duration = int(duration) * 1000
            except: duration = 0

            if available and not locked:

                oc.add(VideoClipObject(
                    url = json['result']['episode']['url'],
                    title = json['result']['episode']['title'],
                    duration = duration,
                    summary = json['result']['episode']['description'],
                    thumb = Resource.ContentsOfURLWithFallback(url=json['result']['episode']['images'][0]['url'])
                ))

        # This handles json for a multiple videos
        else:

            for video in json['result']['items']:

                locked = video['distPolicy']['authTve']

                if locked:
                    continue

                available = video['distPolicy']['available']

                if not available:
                    continue

                vid_url = video['url']
                vid_title = video['title']

                # Found some urls for VGX that have /video-collections/ in the urls 
                # which will fail the url service check, they all consist of just one clips
                # so changing them to '/video-clips/' works and does not cause an error
                if '/video-collections/' in vid_url:
                    vid_url = vid_url.replace('/video-collections/', '/video-clips/')

                thumb = video['images'][0]['url']

                try: episode = int(video['season']['episodeNumber'])
                except: episode = None

                try: season = int(video['season']['seasonNumber'])
                except: season = None

                # Duration for video clips are strings with decimals and full episodes are integers
                # So make both the same format (string) and then convert video clip duration to milliseconds
                duration = video['duration']

                try: duration = int(duration) * 1000
                except:
                    try: duration = int(float(duration)) * 1000
                    except: duration = 0

                summary = video['description']

                if episode:
                    oc.add(EpisodeObject(
                        url = vid_url,
                        title = vid_title,
                        duration = duration,
                        index = episode,
                        season = season,
                        summary = summary,
                        thumb = Resource.ContentsOfURLWithFallback(url=thumb)
                    ))
                else:
                    oc.add(VideoClipObject(
                        url = vid_url,
                        title = vid_title,
                        duration = duration,
                        summary = summary,
                        thumb = Resource.ContentsOfURLWithFallback(url=thumb)
                    ))

            # Add next page code here
            try: next_page = json['result']['nextPageURL']
            except: next_page = None

            if next_page:
                oc.add(NextPageObject(key=Callback(JSONVideoBrowser, url=next_page, title=title), title="Next Page"))

    if len(oc) < 1:
        return ObjectContainer(header="Spike", message="There are currently no videos available.")
    else:
        return oc

####################################################################################################
# This function decides whether a special has video pages
# Special pages do not have json for menus on main page, so using html to pull the sections is the best
@route("/video/spike/specialsections")
def SpecialSections(title, url):

    oc = ObjectContainer(title2=title)

    try:
        html = HTML.ElementFromURL(url, cacheTime=CACHE_1DAY)
    except:
        return ObjectContainer(header="Spike", message="This show does not contain videos.")

    for sections in html.xpath('//div[@id="nav"]/ul/li/a'):

        sec_title = sections.xpath('.//text()')[0]
        sec_url = sections.xpath('./@href')[0]

        if not sec_url.startswith('http:'):
            sec_url = BASE_URL + sec_url

        if '/video-collections/' in sec_url:
            oc.add(DirectoryObject(key=Callback(Sections, url=sec_url, title=sec_title), title=sec_title))

        elif '/episodes/' in sec_url:
            feed_type = 't2_lc_promo1'
            feed_url = JSONFeed(sec_url, feed_type)
            oc.add(DirectoryObject(key=Callback(JSONVideoBrowser, url=feed_url, title=sec_title), title=sec_title))

        else:
            continue

    if len(oc) < 1:
        return ObjectContainer(header="Spike", message="There are no videos available.")
    else:
        return oc

####################################################################################################
# This function pulls the json feed for videos
@route("/video/spike/jsonfeed")
def JSONFeed(url, feed_type=''):

    content = HTTP.Request(url, cacheTime=CACHE_1DAY).content
    # This makes sure the right zone or section is pulled based on the type of page 
    if feed_type: 
        promo = feed_type
    else: 
        promo = 't4_lc_promo1'

    try:
        # A few will not pick up json without looking for '};' at end
        json_data = RE_JSON.search(content).group(1) + '}'
        json = JSON.ObjectFromString(json_data)
        try: video_feed = json['manifest']['zones'][promo]['feed']
        except: video_feed = url
    except: 
        Log('cannot find a json feed')
        video_feed = url

    return video_feed
