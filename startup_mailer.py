import subprocess
import smtplib
import socket
from email.mime.text import MIMEText
import datetime
import os

# Change to your own account information
to_list = ['', '']
for i in range(0,len(to_list)):
    to = to_list[i]
    gmail_user = 'gecapstone1@gmail.com'
    gmail_password = 'GeCapstone'
    smtpserver = smtplib.SMTP('smtp.gmail.com', 587)
    smtpserver.ehlo()
    smtpserver.starttls()
    smtpserver.ehlo
    smtpserver.login(gmail_user, gmail_password)
    today = datetime.date.today()

    # Very Linux Specific
    arg='ip route list'
    p=subprocess.Popen(arg,shell=True,stdout=subprocess.PIPE)
    data = p.communicate()
    split_data = data[0].split()
    ipaddr = split_data[split_data.index('src')+1]

    wifiname = subprocess.Popen(["iwgetid", "-r"], stdout=subprocess.PIPE).communicate()[0]
    my_ip = "Raspberry pi id #1\nWifi Name is {}IP address is {}".format(wifiname, ipaddr)

    msg = MIMEText(my_ip)
    msg['Subject'] = 'IP For RaspberryPi on %s' % today.strftime('%b %d %Y')
    msg['From'] = gmail_user
    msg['To'] = to
    smtpserver.sendmail(gmail_user, [to], msg.as_string())
    smtpserver.quit()
