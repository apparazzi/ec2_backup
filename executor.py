#!/usr/bin/env python

import config
import boto.ec2
import boto.ses
import datetime
import logging
import logging.handlers
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart


logRoatate = logging.handlers.RotatingFileHandler(
    "%s" % config.LOG_FILE,
    maxBytes=5242880,
    backupCount=5
)
logger = logging.getLogger("AWS Backup log")
logger.setLevel(logging.DEBUG)
logger.addHandler(logRoatate)


class Backup:
    conn = None

    def __init__(self):
        self.conn = boto.ec2.connect_to_region(
            config.REGION,
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY
        )

    def do_backups(self):
        volumes = self.conn.get_all_volumes(
            filters={
                'BackupEnable': "True"
            }
        )
        for v in volumes:
            logger.info("Creating snapshot for %s" % v.id)
            snapshot = self.conn.create_snapshot(v.id, "ec2-backup")
            logger.info("Created snapshot %s\n" % snapshot.id)


    def clean_backups(self):
        logger.info("Starting cleanup")
        snapshots = self.conn.get_all_snapshots(
            owner="self",
            filters={
                'description': "ec2-backup"
            }
        )
        for snapshot in snapshots:
            timestamp = datetime.datetime.strptime(snapshot.start_time, "%Y-%m-%dT%H:%M:%S.000Z")
            when_to_delete = (datetime.datetime.now() - datetime.timedelta(days=config.KEEP_DAYS))
            if timestamp < when_to_delete:
                logger.info("Deleting old backup %s" % snapshot.id)
                self.conn.delete_snapshot(snapshot.id)



if __name__ == '__main__':
    u = Backup()
    u.do_backups()
    u.clean_backups()

    msg = MIMEMultipart()
    msg['Subject'] = config.EMAIL_SUBJECT
    msg['From'] = config.SENDER
    msg['To'] = config.RECEIVER
    msg.preamble = 'Multipart message.\n'
    part = MIMEText('AWS Daily Backup Job - Log Attached')
    msg.attach(part)
    part = MIMEApplication(open(config.LOG_FILE, 'rb').read())
    part.add_header('Content-Disposition', 'attachment', filename='AWS_Backup.log')
    msg.attach(part)
 
    # connect to SES
    connection = boto.ses.connect_to_region(
            config.SES_REGION,
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY
        )
 
    # and send the message
    result = connection.send_raw_email(msg.as_string()
        , source=msg['From']
        , destinations=[msg['To']])
    print result
    msgc = "Backup complete at %s" % datetime.datetime.now().strftime("%c")
    print msgc
    logger.info(msg)
