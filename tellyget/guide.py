import os
import re
from bs4 import BeautifulSoup
from m3u_parser import M3uParser

group = [('IPTV-广东电视台',['佛山公共', '佛山综合', '南海频道', '佛山影视', '顺德频道', '广东卫视', '经济科教', '广东体育', '广东珠江', '大湾区卫视', '广东影视', '广东公共', '广东少儿', '广东民生', '嘉佳卡通', '广东新闻', '南方购物', '广东移动', '岭南戏曲', '广东房产', '现代教育', '广东4K']),
          ('IPTV-央视',['CCTV-10','CCTV-11','CCTV-12','CCTV-13','CCTV-14','CCTV-15','CCTV-16','CCTV-17','CCTV-1','CCTV-2','CCTV-3','CCTV-4','CCTV-5','CCTV-5+', 'CCTV-6','CCTV-7','CCTV-8','CCTV-9','CGTN俄语', 'CGTN阿拉伯语', 'CGTN法语', 'CGTN西班牙语', 'CGTN英文记录', 'CGTN英语','CGTN','CCTV4中文国际美洲','CCTV4中文国际欧洲','CCTV4K']),
          ('IPTV-卫视',['湖南卫视','浙江卫视','江苏卫视','北京卫视','深圳卫视','黑龙江卫视','湖北卫视','天津卫视','山东卫视','东方卫视','辽宁卫视','四川卫视','金鹰纪实','重庆卫视','安徽卫视','贵州卫视','东南卫视','上海纪实','河北卫视','江西卫视','吉林卫视','广西卫视','甘肃卫视','河南卫视','云南卫视','海南卫视','金鹰卡通','三沙卫视']),
          ('IPTV-卫视-标清',['厦门卫视', '陕西卫视','山西卫视','内蒙古卫视','青海卫视','宁夏卫视','西藏卫视','新疆卫视','兵团卫视','卡酷动画','炫动卡通','山东教育','财富天下','优漫卡通','吉林延边卫视','延边卫视']),
          ('IPTV-央视网台',['央视精品', '第一剧场', '风云音乐', '兵器科技','电视指南','风云足球','央视台球','高尔夫网球','女性时尚','世界地理','怀旧剧场','风云剧场','早期教育','汽摩','靓妆','老故事','国学']),
          ('其他',['CHC高清电影','爱体育','CETV1','CETV2','CETV4','中国交通','茶','快乐垂钓','IPTV谍战剧场','IPTV相声小品','IPTV野外','IPTV法治','爱电影','经典电影','爱大剧','热播剧场','爱综艺','少儿动画','魅力时尚', '天元围棋', '收视指南','求索纪录','九频同播频道']),
          ]
          
class Guide:
    def __init__(self, args, session, base_url):
        self.args = args
        self.session = session
        self.base_url = base_url

    def get_channels(self):
        channels = []
        filtered_channels = 0
        
        #从git下载全网段的组播列表，以此为基础，把本地抓取的单播地址补充进去。
        url = 'GuangdongIPTV_rtp_all.m3u'
        parser = M3uParser()
        parser.parse_m3u(url, check_live=False, enforce_schema=True)        
        part2 = parser.get_list()
        for m in part2:
            channel = {}
            channel['ChannelName'] = m['name']
            channel['Category'] = m['category'] if m['category'] else "其他"
            channel['ChannelURL'] = m['url'] 
            channel['tvg-name'] = m['tvg']['name'] if m['tvg']['name'] else m['name']
            channel['ChannelID'] = -1
            if self.match_channel_filters(channel):
                filtered_channels += 1
            else:
                channels.append(channel)  
        
        #解析本地iptv抓取的频道列表
        response = self.session.post(self.base_url + '/EPG/jsp/getchannellistHWCTC.jsp')
        txt = response.text.replace(' ', '').replace('＋','+').replace('CCTV5+','CCTV-5+').replace('"吉林延边卫视"','"延边卫视"').replace('"福建东南卫视','"东南卫视').replace('中国教育-1','CETV1').replace('CETV-1','CETV1').replace('zoneoffset=0', 'zoneoffset=480').replace('igmp://', 'rtp://')
        soup = BeautifulSoup(txt, 'html.parser')
        scripts = soup.find_all('script', string=re.compile('ChannelID="[^"]+"'))
        print(f'Found {len(scripts)} channels')
                      
        #对照git的全网段列表，相同rtp地址的条目把单播地址提取出来，加入全网段列表。
        for script in scripts:
            match = re.search(r'Authentication.CTCSetConfig\(\'Channel\',\'(.+?)\'\)', script.string, re.MULTILINE)
            channel_params = match.group(1)
            channel = {}
            for channel_param in channel_params.split('",'):
                key, value = channel_param.split('="')
                channel[key] = value
            g = self.get_group(channel['ChannelName'])
            channel['Category'] = g[0]
            channel['tvg-name'] = g[1]
            udpip, rtspip = channel['ChannelURL'].split('|')
            flag = False
            for cc in channels:
                if cc['ChannelURL'] == udpip:
                    cc['ChannelURL'] = channel['ChannelURL']
                    cc['ChannelID'] = channel['ChannelID']
                    flag = True
                    break
            if not flag:
                if self.match_channel_filters(channel):
                    filtered_channels += 1
                else:
                    channels.append(channel)
            
        print(f'Filtered {filtered_channels} channels')
        removed_sd_candidate_channels = self.remove_sd_candidate_channels(channels)
        print(f'Removed {removed_sd_candidate_channels} SD candidate channels')       
        
        #相同tvg-name合并url        
        new_channels = []
        while channels:
            c = channels.pop(0)
            i = len(channels)-1
            while i >=0 :
                c2 = channels[i]                
                if c2['tvg-name'] == c['tvg-name']:
                    c['ChannelURL'] += '|' + c2['ChannelURL']
                    channels.remove(c2)
                i -= 1
            new_channels.append(c)
        #new_channels.sort(key=lambda x:(x['Category'],x['ChannelName']))               
        return new_channels
        

    def match_channel_filters(self, channel):
        for channel_filter in self.args.filter:
            match = re.search(channel_filter, channel['ChannelName'])
            if match:
                return True
        return False

    def remove_sd_candidate_channels(self, channels):
        if self.args.all_channel:
            return 0
        channels_count = len(channels)
        channels[:] = [channel for channel in channels if not Guide.is_sd_candidate_channel(channel, channels)]
        new_channels_count = len(channels)
        return channels_count - new_channels_count

    @staticmethod
    def is_sd_candidate_channel(channel, channels):
        for c in channels:
            if c['ChannelName'] == channel['ChannelName'] + '高清':
                return True
        return False
    
    def get_group(self, channelname):
        for g in group:
            for x in g[1]:
                if x in channelname:
                    return (g[0], x)
        return ('其他', channelname)
        
    def get_playlist(self, channels):
        if self.args.output[-3:].upper() == 'TXT':
            return self.get_playlist_txt(channels)
        return self.get_playlist_m3u(channels)    
                    
    def get_playlist_m3u(self, channels):
        content = '#EXTM3U\n'
        for channel in channels:
            channelname = channel['ChannelName']
            content += f"#EXTINF:-1 tvg-name=\"{channel['tvg-name']}\" tvg-id=\"{channel['ChannelID']}\" group-title=\"{channel['Category']}\",{channel['ChannelName']}\n"
            urls = channel['ChannelURL'].split('|')
            urls = list(set(urls))
            urls.sort(reverse=True)
            i = 0
            while i < len(urls):
                if 'rtsp' in urls[i]:
                    urls[i] += "$单播"
                else:
                    urls[i] += "$组播"
                i += 1
            urls = '#'.join(urls)
            content += f"{urls}\n".replace('rtp://', 'http://192.168.2.1:4022/rtp/')
        return content
        
    def get_playlist_txt(self, channels):
        current_category = ''
        content = ''
        for channel in channels:
            if channel['Category'] != current_category:
                current_category = channel['Category']
                content += current_category.replace('IPTV-','') + ',#genre#\n'
            content += f"{channel['ChannelName']},"
            urls = channel['ChannelURL'].split('|')
            urls = list(set(urls))
            urls.sort(reverse=True)
            i = 0
            while i < len(urls):
                if 'rtsp' in urls[i]:
                    urls[i] += "$单播"
                else:
                    urls[i] += "$组播"
                i += 1
            urls = '#'.join(urls)
            content += f"{urls}\n".replace('rtp://', 'http://192.168.2.1:4022/rtp/')
        return content

    def save_playlist(self, playlist):
        path = os.path.abspath(self.args.output)
        Guide.save_file(path, playlist)
        print(f'Playlist saved to {path}')

    @staticmethod
    def save_file(file, content):
        os.makedirs(os.path.dirname(file), exist_ok=True)
        with open(file, 'w', encoding="UTF-8") as f:
            f.write(content)
            f.close()
