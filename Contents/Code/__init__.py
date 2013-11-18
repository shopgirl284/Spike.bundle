RE_TITLE = Regex('(.+?) \([0-9]+\)')
RE_SEASON = Regex('Season ([0-9]+)')

BASE_URL = "http://www.spike.com"
SHOW_URL = 'http://www.spike.com/shows'
# 10 Million Dollar Bigfoot Bounty('/shows/bigfoot-bounty') shows no videos because it is a blog
# All Access E3('/shows/32') shows no videos because it redirects to the Gametrailer website
# Bellator Vote for the Fight('/shows/bellator-vote-for-the-fight') doesn't have a video page
SHOW_EXCLUSIONS = ["10 Million Dollar Bigfoot Bounty", "All Access: E3", "Bellator MMA: Vote For The Fight"]

# The variables below are no longer used. The can provide detailed info for individual videos or playlists
#MRSS_PATH = "http://www.comedycentral.com/feeds/mrss?uri=%s"
#MRSS_NS = {"media": "http://search.yahoo.com/mrss/"}
####################################################################################################
def Start():

    ObjectContainer.title1 = "Spike"
    HTTP.CacheTime = CACHE_1HOUR
    HTTP.Headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.7; rv:13.0) Gecko/20100101 Firefox/13.0.1'

####################################################################################################
@handler("/video/spike", "Spike")
def MainMenu():

    oc = ObjectContainer()
    data = HTML.ElementFromURL(SHOW_URL)

    #Shows are pulled from the main show page and this pulls shows from all four sectionslisted
    for shows in data.xpath('//div[@class="middle"]/div/ul/li/a'):
        url = shows.get('href')
        show_title = shows.text.strip()
        if not url.startswith('http:'):
            url = BASE_URL + url
        # If '/shows/' is not in url, they will not work with the proceeding functions, so we send them to a special function
        if '/shows/' not in url:
            oc.add(DirectoryObject(key=Callback(SpecialBrowser, show_url=url, show_title=show_title), title=show_title))
        elif show_title in SHOW_EXCLUSIONS:
            continue
        else:
            oc.add(DirectoryObject(key=Callback(Sections, url=url, title=show_title), title=show_title))

    oc.objects.sort(key = lambda obj: obj.title)
    
    return oc

####################################################################################################
# This function decides whether the show has full episodes, video clips or both and gets the necessary urls
# Since all shows that do not have videos were excluded in the main function, we pull info from the show's video clip page
# This way only one html pull is required to get the video clip feed and check menu for inclusion of a full episode section.
@route("/video/spike/sections")
def Sections(title, url):

    oc = ObjectContainer(title2=title)
    if url.endswith('/'):
        clip_url = url + 'video-clips'
    else:
        clip_url = url + '/video-clips'
    # Shows without a video clip pages should be caught by the main menu exclusion, but this will prevent any issues for shows added in the future 
    try:
        html = HTML.ElementFromURL(clip_url, cacheTime = CACHE_1DAY)
    except:
        return ObjectContainer(header="Spike", message="This show does not contain videos.")
    
    # Then we see if there is an episode guide or episode section and get the feed url for video clips 
    # the feed url for full episodes are pulled in the season function 
    for sections in html.xpath('//div[@class="menu"]/ul/li/a'):
        sec_title = sections.xpath('.//text()')[0]
        if sec_title=='Episode Guide' or sec_title=='Episodes':
            full_url = sections.xpath('.//@href')[0]
            oc.add(DirectoryObject(key=Callback(ShowBrowser, show_url=full_url, show_title="Full Episodes"), title="Full Episodes"))
        # Prior to excluding shows without video pages, one of those shows that did not have a video section did not give a 404 error in this function, 
        # so put this pull of video clip feed in an elif to help prevent any issues for shows added in the future 
        elif sec_title=='Video Clips' or sec_title=='Videos':
            clip_feed_url = html.xpath('//div[@class="v_content"]//@data-url')[0]
            oc.add(DirectoryObject(key=Callback(ClipBrowser, show_url=clip_feed_url, show_title="Video Clips"), title="Video Clips"))
        else:
            continue

    if len(oc) == 0:
        return ObjectContainer(header="Spike", message="There are no compatible videos available for %s." %show_title)
    
    return oc
####################################################################################################
# This function breaks full episodes down into seasons
# Only full episodes are listed by season because season links on the episode pages give the feed link by season
# Video clip pages only give the feed links for all clips, and then give the data-item for each season
@route("/video/spike/showbrowser")
def ShowBrowser(show_url, show_title):

    oc = ObjectContainer(title2=show_title)

    if not show_url.startswith('http://'):
        show_url = BASE_URL + show_url

    data = HTML.ElementFromURL(show_url)

    for season in data.xpath('//ul[@class="season_navigation"]//a'):
        season_title = season.text
        season_url = season.get('href')
        oc.add(DirectoryObject(key=Callback(EpisodeBrowser, show_title=show_title, season_url=season_url, season_title=season_title), title=season_title))

    if len(oc) == 1:
        return EpisodeBrowser(show_title=show_title, season_url=season_url)

    return oc

####################################################################################################
@route("/video/spike/episodebrowser")
def EpisodeBrowser(show_title, season_url, season_title=None):

    oc = ObjectContainer(title1=show_title, title2=season_title)

    try:
        season_index = RE_SEASON.search(season_title).group(1)
    except:
        season_index = None

    data = HTML.ElementFromURL(season_url)

    for ep in data.xpath('//div[contains(@class, "episode_guide")]'):
        try:
            ep_url = ep.xpath('.//a[@class="title"]')[0].get('href')
        except:
            continue
        episode_type = ep.xpath('.//div[@class="full"]//span[@class="title"]')[0].text
        Log(episode_type)
        if episode_type == "episode highlights":
            #highlight reels don't work with the URL Service for some reason and who wants to watch
            #episode highlights anyway. Exclude that sh!t from the episode list.
            continue

        ep_title = ep.xpath('.//img')[0].get('title')
        ep_thumb = ep.xpath('.//img')[0].get('src').split('?')[0]
        ep_summary = ep.xpath('.//div[@class="description"]//p')[0].text.strip()

        if season_index:
            ep_index = ep_url.split('-')[-1].replace(season_index, '', 1).lstrip('0').strip('s')
        else:
            ep_index = ep_url.split('-')[-1].strip('s')
        # found that one ep_index was giving an error due to being empty so added exception
        if not ep_index:
            ep_index=0
        ep_airdate = ep.xpath('.//p[@class="aired_available"]/text()')[0].strip()
        ep_date = Datetime.ParseDate(ep_airdate).date()
		
        if season_index:
            oc.add(EpisodeObject(url=ep_url, title=ep_title, show=show_title, summary=ep_summary, index=int(ep_index), season=int(season_index),
                originally_available_at=ep_date, thumb=Resource.ContentsOfURLWithFallback(url=ep_thumb)))
        else:
            oc.add(EpisodeObject(url=ep_url, title=ep_title, show=show_title, summary=ep_summary, absolute_index=int(ep_index),
                originally_available_at=ep_date, thumb=Resource.ContentsOfURLWithFallback(url=ep_thumb)))
	
    try:
        next_page = data.xpath('//div[@class="pagination"]//a')[-1]
        if next_page.text == 'Next':
            next_url = next_page.get('href')
            oc.add(NextPageObject(key=Callback(EpisodeBrowser, show_title=show_title, season_url=next_url, season_title=season_title), title="Next Page"))
    except:
        pass
	
    if len(oc) == 0:
        return ObjectContainer(header="Spike", message="There are currently no episodes available for %s." %show_title)
	
    return oc

####################################################################################################
@route("/video/spike/clipbrowser")
def ClipBrowser(show_url, show_title):
    oc = ObjectContainer(title2=show_title)
	
    if show_url.startswith('http://'):
        pass
    else:
        show_url = BASE_URL + show_url

    data = HTML.ElementFromURL(show_url)
    for clip in data.xpath('//div[@id="show_clips_res"]//div[@class="block"]'):
        clip_url 	= clip.xpath('.//a')[0].get('href')
        clip_thumb 	= clip.xpath('.//img')[0].get('src').split('?')[0]
        clip_title 	= clip.xpath('.//h3/a')[0].text
        clip_runtime	= clip.xpath('.//h3/small')[0].text.strip('(').strip(')')
        clip_duration	= Datetime.MillisecondsFromString(clip_runtime)
        try:
            posted_date = clip.xpath('.//div[@class="af_content"]/small')[0].text.strip('Posted ')
            clip_date = Datetime.ParseDate(posted_date).date()
        except:
            clip_date = None
        clip_summary = clip.xpath('.//div[@class="af_content"]/p')[0].text

        oc.add(VideoClipObject(url=clip_url, title=clip_title, summary=clip_summary, duration=clip_duration, originally_available_at=clip_date,
            thumb=Resource.ContentsOfURLWithFallback(url=clip_thumb)))

    try:
        # For some reason the paging for the feeds for video clips do not always have the full and proper url in the paging
        # So we have to determine the current page number and see if there is a next page number and add that next page number to the existing feed url
        if '?' in show_url:
            feed_page = show_url.split('?')[0]
        else:
            feed_page = show_url
        all_pages = data.xpath('//div[@class="pagination"]/div/ul/li/a//text()')
        next_page = int(data.xpath('//div[@class="pagination"]/div/ul/li/span//text()')[0]) + 1
        next_page = str(next_page)
        if next_page in all_pages:
            next_url = feed_page + '?page=' + next_page
            oc.add(NextPageObject(key=Callback(ClipBrowser, show_url=next_url, show_title=show_title), title="Next Page"))
    except:
        pass
        
    if len(oc) == 0:
        return ObjectContainer(header="Spike", message="There are currently no video clips available for %s." %show_title)

    return oc
####################################################################################################
# This function is for handling specials that do not fit into the normal video format
@route("/video/spike/specialbrowser")
def SpecialBrowser(show_url, show_title):

    oc = ObjectContainer(title2=show_title)

    data = HTML.ElementFromURL(show_url)
    clip_feeds = []
    thumb = data.xpath('//meta[@property="og:image"]//@content')[0].split('?')[0]
    
    for item in data.xpath('//div[@class="item"]/a'):
        item_url = item.xpath('.//@href')[0]
        if not item_url.startswith('http:'):
            item_url = BASE_URL + item_url
        if '/episodes/' in item_url:
            item_title = item.xpath('./img//@title')[0]
            oc.add(VideoClipObject(title=item_title, url=item_url, thumb=Resource.ContentsOfURLWithFallback(url=thumb)))
        if '/video-clips/' in item_url:
            html = HTML.ElementFromURL(item_url)
            clip_feed_url = html.xpath('//div[@class="v_content"]//@data-url')[0]
            if clip_feed_url not in clip_feeds:
                clip_feeds.append(clip_feed_url)
                oc.add(DirectoryObject(key=Callback(ClipBrowser, show_url=clip_feed_url, show_title=item_title), title="Related Video Clips", thumb=Resource.ContentsOfURLWithFallback(url=thumb)))

    if len(oc) == 1:
        return ObjectContainer(header="Spike", message="There are no compatible videos available for %s." %show_title)

    return oc

