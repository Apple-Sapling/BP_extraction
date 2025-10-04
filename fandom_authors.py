#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

"""

from bs4 import BeautifulSoup
import time
import requests
import csv
import sys
import datetime
import argparse
import os
import re

page_empty = False
url = ""
num_requested_authors = 0
num_recorded_authors = 0
csv_name = ""
continue_csv = False
seen_ids = set()

def get_args():
    global url
    global csv_name
    global num_requested_authors
    global continue_csv

    parser = argparse.ArgumentParser(description='Scrape AO3 authors given a people search URL')
    parser.add_argument('url', metavar='URL', help='a single URL pointing to an AO3 search page')
    parser.add_argument('--out_csv', default='author_ids', help='csv output file name')
    parser.add_argument('--header', default='', help='user http header')
    parser.add_argument('--continue_csv', default='', help='pick up where the csv file left off')
    parser.add_argument('--num_to_retrieve', default='20', help='how many author ids you want')

    args = parser.parse_args()
    url = args.url
    csv_name = str(args.out_csv)
    continue_csv = bool(args.continue_csv)
    num_requested_authors = int(args.num_to_retrieve)
    header_info = str(args.header)

    return header_info

def get_ids(header_info=''):
    global page_empty
    global seen_ids

    headers = {'user-agent': header_info}
    req = requests.get(url, headers=headers)
    while req.status_code == 429:
        print("Request answered with Status-Code 429, waiting before retrying...")
        print(f"Info: {url}")
        time.sleep(10)
        req = requests.get(url, headers=headers)

    soup = BeautifulSoup(req.text, "lxml")
    sys.stdout.write('.')
    sys.stdout.flush()
    authors = soup.select("li.user > .header:first-child")

    if len(authors) == 0:
        page_empty = True

    ids = []
    for author_blurb in authors:
        author = extract_author_info(author_blurb)
        if author['id'] not in seen_ids:
            ids.append(author)
            seen_ids.add(author['id'])
    return ids

def href(element):
    if element is None:
        return ""
    url = element['href']
    if url.startswith("http"):
        return url
    return "https://archiveofourown.org" + url

def extract_author_info(author_blurb):
    a_s = author_blurb.select('h4 a')
    author_a = None
    pseud_a = None
    for a in a_s:
        if "/pseuds/" in a['href']:
            pseud_a = a
        else:
            author_a = a

    ## Get number of works (all works + in fandom/tag)
    works_select = author_blurb.select('h5 a')
    works_fandom, works_all, bookmarks = None, None, None
    for a in works_select:
        text = a.text
        if ' in ' in text:
            works_fandom = text
        elif 'bookmark' in text:
            bookmarks = text
        else:
            works_all = text
    
    ## get the number value from text
    works_fandom = re.search(r'\d+', works_fandom).group() if works_fandom else 0
    works_all = re.search(r'\d+', works_all).group() if works_all else 0
    bookmarks = re.search(r'\d+', bookmarks).group() if bookmarks else 0

    if author_a is None:
        author_a = pseud_a
        pseud_a = None

    author = {"author": author_a.text, "author_link": href(author_a)}
    if pseud_a is not None:
        author["pseud"] = pseud_a.text
        author["pseud_link"] = href(pseud_a)
    else:
        author["pseud"] = ""
        author["pseud_link"] = ""
    author["id"] = f"{author['author']}/{author['pseud']}"

    author["works_all"]= works_all
    author["works_in_fandom"]=works_fandom
    author["bookmarks"]=bookmarks
    return author

def update_url_to_next_page():
    global url
    key = "page="
    start = url.find(key)

    if start != -1:
        page_start_index = start + len(key)
        page_end_index = url.find("&", page_start_index)
        if page_end_index != -1:
            page = int(url[page_start_index:page_end_index]) + 1
            url = url[:page_start_index] + str(page) + url[page_end_index:]
        else:
            page = int(url[page_start_index:]) + 1
            url = url[:page_start_index] + str(page)
    else:
        url += "&page=2" if "?" in url else "?page=2"

def write_ids_to_csv(ids):
    global num_recorded_authors
    with open(csv_name + ".csv", 'a', newline="", encoding="utf-8") as csvfile:
        wr = csv.writer(csvfile, delimiter=',')
        for id in ids:
            wr.writerow([id['author'], id['pseud'], id['author_link'], id['pseud_link'], id["works_all"], id["works_in_fandom"], id["bookmarks"]])
            num_recorded_authors += 1

def not_finished():
    if page_empty:
        return False
    return num_requested_authors == -1 or num_recorded_authors < num_requested_authors

def make_readme():
    with open(csv_name + "_readme.txt", "a", encoding="utf-8") as text_file:
        text_file.write(f"\nretrieved on: {datetime.datetime.now()}\nnum_requested_authors: {num_requested_authors}\nurl: {url}\n")

def reset():
    global page_empty
    global num_recorded_authors
    page_empty = False
    num_recorded_authors = 0

def process_for_ids(header_info=''):
    while not_finished():
        time.sleep(5)  # 5-second delay to respect AO3's TOS
        ids = get_ids(header_info)
        write_ids_to_csv(ids)
        update_url_to_next_page()

def load_existing_ids():
    global seen_ids
    global url
    global continue_csv

    new_url = ""
    if os.path.exists(csv_name + ".csv"):
        print("Loading existing IDs to avoid duplicates...\n")
        with open(csv_name + ".csv", 'r', encoding="utf-8") as csvfile:
            id_reader = csv.reader(csvfile)
            for row in id_reader:
                seen_ids.add(f"{row[0]}/{row[1]}")
    else:
        print("No existing file found; creating new file...\n")
        with open(csv_name + ".csv", 'a', newline="", encoding="utf-8") as csvfile:
            wr = csv.writer(csvfile, delimiter=',')
            wr.writerow(['author', 'pseud', 'author link', 'pseud link', 'works', 'works in fandom', 'bookmarks'])

def main():
    header_info = get_args()
    make_readme()
    print("Loading existing file...\n")
    load_existing_ids()
    print("Processing...\n")
    process_for_ids(header_info)
    print("Done.")

main()
