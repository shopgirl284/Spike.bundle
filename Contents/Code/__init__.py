RE_TITLE 	= Regex('(.+?) \([0-9]+\)')
RE_SEASON	= Regex('Season ([0-9]+)')

BASE_URL 	= "http://www.spike.com"
MRSS_PATH 	= "http://www.comedycentral.com/feeds/mrss?uri=%s"
MRSS_NS 	= {"media": "http://search.yahoo.com/mrss/"}

ICON 		= "icon-default.png"
ART 		= "art-default.jpg"

####################################################################################################
def Start():
	ObjectContainer.art = R(ART)
	DirectoryObject.thumb = R(ICON)
	ObjectContainer.title1 = "Spike"

	HTTP.CacheTime = CACHE_1HOUR
	HTTP.Headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.7; rv:13.0) Gecko/20100101 Firefox/13.0.1'

####################################################################################################
@handler("/video/spike", "Spike", ICON, ART)
def MainMenu():

	oc = ObjectContainer()

	oc.add(DirectoryObject(key=Callback(ShowList, group="Full Episodes", url='/full-episodes/'), title="Full Episodes"))
	oc.add(DirectoryObject(key=Callback(ShowList, group="Video Clips", url='/video-clips/'), title="Clips"))
	oc.add(DirectoryObject(key=Callback(ShowList, group="Web Series", url='/video-clips/'), title="Web Series"))

	return oc

####################################################################################################
@route("/video/spike/showlist")
def ShowList(group, url):
	oc = ObjectContainer(title2=group)

	list_url = BASE_URL + url
	
	data = HTML.ElementFromURL(list_url)
	if group == "Video Clips":
		index = 0
	elif group == "Web Series":
		index = 1
	show_list = data.xpath('//div[@class="background_sibling"]//ul')[1]
	for show in show_list.xpath('./li/a'):
		show_url = show.get('href')
		show_title = RE_TITLE.search(show.text).group(1)
		if url == '/full-episodes/':
			oc.add(DirectoryObject(key=Callback(ShowBrowser, show_url=show_url, show_title=show_title), title=show_title))
		elif url == '/video-clips/':
			oc.add(DirectoryObject(key=Callback(ClipBrowser, show_url=show_url, show_title=show_title), title=show_title))
		
	return oc

####################################################################################################
@route("/video/spike/showbrowser")
def ShowBrowser(show_url, show_title):
	oc = ObjectContainer(title2=show_title)
	
	data = HTML.ElementFromURL(show_url)
	for season in data.xpath('//ul[@class="season_navigation"]//a'):
		season_title 	= season.text
		season_url 	= season.get('href')
		oc.add(DirectoryObject(key=Callback(EpisodeBrowser, show_title=show_title, season_url=season_url, season_title=season_title), title=season_title))
	
	if len(oc) == 1:
		return EpisodeBrowser(show_title=show_title, season_url=season_url)
	return oc

####################################################################################################
@route("/video/spike/episodebrowser")
def EpisodeBrowser(show_title, season_url, season_title=None):
	oc = ObjectContainer(title1=show_title, title2=season_title)
	
	if season_title:
		season_index = RE_SEASON.search(season_title).group(1)
	else:
		season_index = None
	
	data = HTML.ElementFromURL(season_url)
	for ep in data.xpath('//div[contains(@class, "full_episode ")]'):
		try:
			ep_url	= ep.xpath('.//a[@class="title"]')[0].get('href')
		except:
			continue
		ep_title 	= ep.xpath('.//img')[0].get('title')
		ep_thumb	= ep.xpath('.//img')[0].get('src').split('?')[0]
		ep_summary	= ep.xpath('.//div[@class="short_desc"]//p')[0].text.strip()
		try:
			ep_runtime	= ep.xpath('.//span[@class="run_time"]')[0].text.strip('(').strip(')')
			ep_duration	= Datetime.MillisecondsFromString(ep_runtime)
		except:
			ep_runtime	= None
		if season_index:
			ep_index	= ep_url.split('-')[-1].replace(season_index, '', 1).lstrip('0')
		else:
			ep_index	= ep_url.split('-')[-1]
		ep_airdate	= ep.xpath('.//p[@class="aired_available"]/text()')[1]
		ep_date 	= Datetime.ParseDate(ep_airdate).date()
		
		if season_index:
			oc.add(EpisodeObject(url=ep_url, title=ep_title, show=show_title, summary=ep_summary, duration=ep_duration, index=int(ep_index), season=int(season_index),
				originally_available_at=ep_date, thumb=Resource.ContentsOfURLWithFallback(url=ep_thumb, fallback=ICON)))
		else:
			oc.add(EpisodeObject(url=ep_url, title=ep_title, show=show_title, summary=ep_summary, duration=ep_duration, absolute_index=int(ep_index),
				originally_available_at=ep_date, thumb=Resource.ContentsOfURLWithFallback(url=ep_thumb, fallback=ICON)))
	
	try:
		next_page = data.xpath('//div[@class="pagination"]//a')[-1]
		if next_page.text == 'Next':
			next_url = next_page.get('href')
			oc.add(NextPageObject(key=Callback(EpisodeBrowser, show_title=show_title, season_url=next_url, season_title=season_title), title="Next Page", thumb=R(ICON)))
	except:
		pass
	
	return oc

####################################################################################################
@route("/video/spike/clipbrowser")
def ClipBrowser(show_url, show_title):
	oc = ObjectContainer(title2=show_title)
	
	data = HTML.ElementFromURL(show_url)
	for clip in data.xpath('//div[@id="show_clips_res"]//div[@class="block"]'):
		clip_url 	= clip.xpath('.//a')[0].get('href')
		Log(clip_url)
		clip_thumb 	= clip.xpath('.//img')[0].get('src').split('?')[0]
		Log(clip_thumb)
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
			thumb=Resource.ContentsOfURLWithFallback(url=clip_thumb, fallback=ICON)))

	try:
		next_page = data.xpath('//div[@class="pagination"]//a')[-1]
		if next_page.text == 'Next':
			next_url = next_page.get('href')
			oc.add(NextPageObject(key=Callback(ClipBrowser, show_url=next_url, show_title=show_title), title="Next Page", thumb=R(ICON)))
	except:
		pass
	
	return oc
