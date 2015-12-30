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
import glob
import os
import smtplib
import yaml

from lxml import etree, html


# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

URL = 'http://www.senate.gov/employment/po/positions.htm'
FNAME = os.path.join(os.sep, 'tmp', 'senatejobs', 'jobs.{d:%Y%m%d%H%m}.csv')
FLAST = os.path.join(os.sep, 'tmp', 'senatejobs', 'jobs.[0-9]*.csv')
NOW = datetime.datetime.now()
FNOW = FNAME.format(d=NOW)
FROMADDR = "R. Zach Lamberty <r.zach.lamberty@gmail.com>"
SERVER = 'smtp.gmail.com'
FCRED = os.path.expanduser(os.path.join('~', '.secrets', 'gmail.yaml'))


# ----------------------------- #
#   Main routine                #
# ----------------------------- #

def main(url=URL, flast=FLAST, fout=FNOW, mailto=None, server=SERVER,
         credfile=FCRED, mailempty=False):
    ystpos = load_most_recent_positions(flast)
    nowpos = get_positions(url)
    newpos = [
        pos for pos in nowpos
        if not pos['id'] in [oldpos['id'] for oldpos in ystpos]
    ]
    publish(
        newpos=newpos,
        fout=fout,
        mailto=mailto,
        server=server,
        credfile=credfile,
        mailempty=mailempty
    )


def load_most_recent_positions(flast=FLAST):
    try:
        mostrecent = max(glob.glob(flast), key=lambda f: os.path.getmtime(f))
        with open(mostrecent, 'r') as f:
            return list(csv.DictReader(f))
    except ValueError:
        print "no files matching {}, moving on".format(flast)
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


def publish(newpos, fout=FNOW, mailto=None, server=SERVER, credfile=FCRED,
            mailempty=False):
    # file only gets written if newpos exists; email goes out either way (but
    # only if mailto exists)
    subject = "New Senate Jobs {:%F %X}".format(NOW)
    body = email_body(newpos)
    files = []
    if newpos and fout:
        fdir = os.path.dirname(fout)
        if not os.path.exists(fdir):
            os.makedirs(fdir)

        with open(fout, 'wb') as f:
            c = csv.DictWriter(f, fieldnames=newpos[0].keys())
            c.writeheader()
            c.writerows(newpos)
        files.append(fout)
    if mailto and (newpos or mailempty):
        print "Sending email to {}".format(mailto)
        send_mail(
            to=mailto, subject=subject, body=body, files=files, server=SERVER,
            credfile=credfile
        )


def email_body(newpos):
    if newpos:
        return '<html><head></head><body>{tables:}</body></html>'.format(
            tables=''.join(p['html'] for p in newpos)
        )
    else:
        return "No new jobs"


def send_mail(to, subject, body, files=[], server=SERVER, port=587,
              credfile=FCRED):
    msg = email.mime.multipart.MIMEMultipart()
    msg['From'] = FROMADDR
    msg['To'] = email.utils.COMMASPACE.join(to)
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

    smtp = smtplib.SMTP(server, port)
    smtp.ehlo()
    smtp.starttls()
    if credfile:
        with open(credfile, 'rb') as f:
            cred = yaml.load(f)
        smtp.login(cred['user'], cred['password'])
    smtp.sendmail(FROMADDR, to, msg.as_string())
    smtp.close()


# ----------------------------- #
#   Command line                #
# ----------------------------- #

def parse_args():
    """ Take a log file from the commmand line """
    parser = argparse.ArgumentParser()

    mailto = 'list of email addresses to which we should send results'
    parser.add_argument("-m", "--mailto", help=mailto, nargs="+")

    server = "smtp server address"
    parser.add_argument("-s", "--server", help=server, default=SERVER)

    credfile = "path to credentials (yaml file with 'user', and 'password' keys)"
    parser.add_argument("-c", "--credfile", help=credfile, default=FCRED)

    mailempty = "Mail even if the results are empty (no new postings)"
    parser.add_argument("--mailempty", help=mailempty, action='store_true')

    return parser.parse_args()


if __name__ == '__main__':

    args = parse_args()
    main(
        url=URL,
        flast=FLAST,
        fout=FNOW,
        mailto=args.mailto,
        server=args.server,
        credfile=args.credfile,
        mailempty=args.mailempty
    )
