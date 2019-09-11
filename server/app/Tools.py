from collections import defaultdict
from html.parser import HTMLParser
from app.DataBase import create_lga, CrimeStatisticsOfLGA
from flask import url_for, request
from xml.etree import ElementTree as et
from dicttoxml import dicttoxml
from datetime import datetime
from flask import jsonify, Response
import csv, re, requests, threading

AUTHOR = {
    'name': 'Xiyan Wang',
    'email': 'z5151289@student.unsw.edu.au'
}

class LinksParser(HTMLParser):
    filelist = []
    def __init__(self):
        HTMLParser.__init__(self)
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for (variable, value) in attrs:
                if variable == "href":
                    if value.startswith('/Documents/RCS-Annual/'):
                        LinksParser.filelist.append(value[value.rfind('/') + 1:])

class CreateLGAThread (threading.Thread):
    def __init__(self, id, lga_filename, updated_time):
        threading.Thread.__init__(self)
        self.id = id
        self.lga = lga_filename
        self.updated = updated_time

    def run(self):
        create_lga(self.lga, self.id, self.updated)

def initialize_users ():
    return {
        'admin': 'admin',
        'guest': 'guest'
    }

def get_filelist ():
    content = requests.get('http://www.bocsar.nsw.gov.au/Pages/bocsar_crime_stats/bocsar_lgaexceltables.aspx').content
    lp = LinksParser()
    lp.feed(content.decode('utf-8'))
    lp.close()
    return LinksParser.filelist

def get_max_id ():
    return max([e.id for e in CrimeStatisticsOfLGA.objects]) if len(CrimeStatisticsOfLGA.objects) != 0 else 0

def get_postcode_info ():
    postcode_dict = defaultdict(list)
    with open('../data/post_code.csv', 'r') as f:
        rows = csv.reader(f)
        for row in rows:
            if (row[0] == 'New South Wales'):
                postcode_dict[str(int(row[2]))].append(row[1])
    return postcode_dict

def get_matched_filenames (lgas, filelist):
    exist_lgas = [[lga.id, lga.title, lga.updated] for lga in CrimeStatisticsOfLGA.objects]
    exist_list = []
    not_found_list = []
    matched_list = []
    for lga in lgas:
        for e in exist_lgas:
            if format_lga(lga) == format_lga(e[1]):
                e[1] = lga
                exist_list.append(e)
                break
        else:
            if format_lga(lga) in [format_lga(f) for f in filelist]:
                matched_list.append(lga)
            else:
                not_found_list.append(lga)
    return matched_list, exist_list, not_found_list

def check_entry_id (entry_id):
    if not entry_id.isdigit():
        return False
    if not CrimeStatisticsOfLGA.objects(id=int(entry_id)):
        return False
    return True

def format_lga (lga):
    lga = lga.replace(' ', '').lower()
    if lga.endswith('lga.xlsx'):
        return lga[:-1 * (len('lga.xlsx'))]
    if lga.endswith(' Local Government Area'):
        return lga[:-1 * (len(' Local Government Area'))]
    return lga

def add_url_to_entries(entries):
    for entry in entries:
        link = {
            'href': url_for('get_one_entry', entry_id=entry['id'], _external=True),
            'rel': 'self'
        }
        entry['link'] = link

def indent_element(e, depth, last):
    indent = "\n" + depth * "    "
    if len(e): # Has children
        if not e.text or not e.text.strip():
            e.text = indent + "    "
        if not e.tail or not e.tail.strip():
            e.tail = indent
        for i in range(len(e)):
            indent_element(e[i], depth + 1, i == len(e) - 1)
        if not e.tail or not e.tail.strip():
            if last:
                e.tail = indent[:-4]
            else:
                e.tail = indent
    else: # No children
        if depth and (not e.tail or not e.tail.strip()):
            if last:
                e.tail = indent[:-4]
            else:
                e.tail = indent

def atom_feed_from_crime_statistics_of_lga (entries, info):
    feed = et.Element('feed', attrib={'xmlns': "http://www.w3.org/2005/Atom"})
    id = et.Element('id')
    id.text = '+'.join(request.url.split())
    feed.append(id)
    title = et.Element('title')
    title.text = 'NSW Recorded Crime Statistics'
    subtitle = et.Element('subtitle')
    subtitle.text = info
    feed.append(subtitle)
    feed.append(title)
    updated = et.Element('updated')
    updated.text = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
    feed.append(updated)
    author = et.fromstring(re.sub(' type=\"[^\"]+\"', '', dicttoxml(AUTHOR, custom_root='author').decode("utf-8")))
    feed.append(author)
    link = et.Element('link', {'rel': 'self', 'href': '+'.join(request.url.split())})
    feed.append(link)
    for entry in entries:
        entry = et.fromstring(re.sub(' type=\"[^\"]+\"', '', dicttoxml(entry, custom_root='entry').decode("utf-8")))
        id = entry.find('id')
        origin_id = id.text
        id.text = url_for('get_one_entry', entry_id=origin_id, _external=True)
        content = entry.find('content')
        if len(content) == 0:
            content.set('type', 'text')
        else:
            content.set('type', 'application/xml')
        feed.append(entry)
    indent_element(feed, 0, True)
    return '<?xml version="1.0" encoding="utf-8"?>\n' + et.tostring(feed).decode('utf-8')

def response_for(entries, info, accept):
    if accept == 'application/json':
        if entries:
            add_url_to_entries(entries)
            response = jsonify(info=info, entries=entries, result_size=len(entries))
            response.headers._list.append(('Access-Control-Allow-Origin','*'))
            return response
        response = jsonify(info=info)
        response.headers._list.append(('Access-Control-Allow-Origin', '*'))
        return response
    return Response(atom_feed_from_crime_statistics_of_lga(entries, info), headers={'Access-Control-Allow-Origin': '*'})