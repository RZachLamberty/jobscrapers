#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: senate_jobs.py
Author: zlamberty
Created: 2015-12-14

Description:
    simple scraper to check jobs posted on the US Senate employment bulletin
    board against those placed yesterday

Usage:
    <usage>

"""

import argparse
import csv
import datetime
import email.encoders
import email.mime.base
import email.mime.multipart
import email.mime.text
import email.utils
import os
import smtplib

from lxml import etree, html


# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

URL = 'http://www.senate.gov/employment/po/positions.htm'
FNAME = os.path.join(os.sep, 'tmp', 'senatejobs', 'jobs.{d:%Y%m%d}.csv')
TDY = datetime.datetime.now()
YST = datetime.datetime.now() - datetime.timedelta(days=1)
FTDY = FNAME.format(d=TDY)
FYST = FNAME.format(d=YST)
CS = email.utils.COMMASPACE
FROMADDR = "R. Zach Lamberty <r.zach.lamberty@gmail.com>"


# ----------------------------- #
#   Main routine                #
# ----------------------------- #

def main(url=URL, fystpos=FYST, ftdypos=FTDY, mailto=None):
    """ docstring """
    ystpos = load_yesterdays_positions(fystpos)
    nowpos = get_positions(url)
    newpos = [
        pos for pos in nowpos
        if not pos['id'] in [pos['id'] for pos in ystpos]
    ]
    publish(newpos, ftdypos, mailto)


def load_yesterdays_positions(fystpos=None):
    try:
        with open(fystpos, 'r') as f:
            return list(csv.DictReader(f))
    except IOError:
        print "no file named {}, moving on".format(fystpos)
        return []


def get_positions(url=URL):
    x = html.parse(url)
    jobs = []
    for tab in x.xpath('//td[@class="contenttext"]/table'):
        try:
            job = {}
            job['id'] = tab.find('tr/td[@valign="top"]/b').text
            job['title'] = tab.xpath('tr/td[not(@valign) and @class="po_employment"]/b')[0].text
            job['desc'] = tab.xpath('tr/td[not(@valign) and @class="po_employment"]/p')[0].text
            for k in ['title', 'desc']:
                # clean up text
                job[k] = job[k].encode('utf-8').strip()
            job['html'] = etree.tostring(tab)
            jobs.append(job)
        except AttributeError:
            print "skipping non-matching tab"
    return jobs


def publish(newpos, ftdypos=FTDY, mailto=None):
    # file only gets written if newpos exists; email goes out either way (but
    # only if mailto exists)
    subject = "New Senate Jobs {:%F}".format(TDY)
    body = email_body(newpos)
    files = []
    if newpos and ftdypos:
        fdir = os.path.dirname(ftdypos)
        if not os.path.exists(fdir):
            os.makedirs(fdir)

        with open(ftdypos, 'wb') as f:
            c = csv.DictWriter(f, fieldnames=newpos[0].keys())
            c.writeheader()
            c.writerows(newpos)
        files.append(ftdypos)
    if mailto:
        send_mail(to=mailto, subject=subject, body=body, files=files)


def email_body(newpos):
    if newpos:
        return '<html><head></head><body>{tables:}</body></html>'.format(
            tables=''.join(p['html'] for p in newpos)
        )
    else:
        return "No new jobs"


def send_mail(to, subject, body, files=[], server="localhost"):
    msg = email.mime.multipart.MIMEMultipart()
    msg['From'] = FROMADDR
    msg['To'] = CS.join(to)
    msg['Subject'] = subject
    msg.attach(
        email.mime.text.MIMEText(body, 'html')
    )

    for fin in files:
        with open(fin, 'rb') as f:
            part = email.mime.base.MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            email.encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                'attachment; filename="{:}"'.format(os.path.basename(fin))
            )
            msg.attach(part)

    smtp = smtplib.SMTP(server)
    smtp.sendmail(FROMADDR, to, msg.as_string())
    smtp.quit()


# ----------------------------- #
#   Command line                #
# ----------------------------- #

def parse_args():
    """ Take a log file from the commmand line """
    parser = argparse.ArgumentParser()

    mailto = 'list of email addresses to which we should send results'
    parser.add_argument("-", "--mailto", help=mailto, nargs="+")

    return parser.parse_args()


if __name__ == '__main__':

    args = parse_args()
    main(
        url=URL,
        fystpos=FYST,
        ftdypos=FTDY,
        mailto=args.mailto
    )
