#!/usr/bin/env python2.7

'''Generates a bash script'''

import argparse
import subprocess
import urllib2
from HTMLParser import HTMLParser
from distutils.version import LooseVersion

parser = argparse.ArgumentParser(description="Ubuntu Mainline Kernel installer generator")
parser.add_argument('--rc', action='store_true', help="ignore Release Canidate versions")
parser.add_argument('-v', help="specify version series eg: 3.8")
parser.add_argument('-r', help="overrides the release version eg: raring")
parser.add_argument('-k', action='store_true', help="generate a installer regardless of the current running kernel")
args = parser.parse_args()

try:
    lsb_release = subprocess.check_output(('lsb_release', '-sc'))
    uname = subprocess.check_output(('uname', '-r')).rstrip('\n')
except subprocess.CalledProcessError as e:
    print e
    exit()

if not args.r:
    args.r = lsb_release

if not args.k:
    k = uname
else:
    k = '1.0.0-1-generic' #Very low fake kernel version to ensure new kernel is found

links = []
url = "http://kernel.ubuntu.com/~kernel-ppa/mainline/"

def fetch_html(url):
    html = urllib2.urlopen(url).read()
    if not html:
        ii = 0
        while ii < 21:
            html = urllib2.urlopen(url).read()
            if not html:
                subprocess.call(('notify-send', '--icon', 'error', 'Kernel Update Checker', 'Unable to connect to kernel.ubuntu.com\\nAttempt %d/20' % ii))
            else:
                break
            subprocess.call(('sleep', '11'))
            ii += 1
    if not html:
        print "echo 'No Internet Access\nexit'"
        exit()
    return html

# This should be handled better
def append_links(info):
    links.append(info)

class LinkParser(HTMLParser):
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr in attrs:
                if attr[0] == 'href':
                   append_links(attr[1])

print "#!/bin/bash"
print "\necho 'Config Notes:'"
print "echo -e '\\t",
print "Rejecting" if not args.rc else "Accepting",
print "Release Canidates'"
print "echo -e '\\t Accepting Latest",
print "%s" % args.v if args.v else "\\b",
print "Kernel'"
print "echo -e '\\t Accepting kernels compiled for %s'" % args.r
print "echo -e '\\t Accepting kernels with version higher than %s'" % k

# Fetch dir listing
html = fetch_html(url)
p = LinkParser()
p.feed(html)

arr = []
arr2 = []
k = k.split('-')
# Find highest applicable version
for l in links:
    name = l.lstrip('v').rstrip('/')
    if args.r in name:
        if not args.rc and '-rc' in name:
            continue
        if args.v and args.v not in name:
            continue
        if LooseVersion(name) > LooseVersion(k[0]):
            name2 = name.rstrip('-%s' % args.r)
            k[0] = name2
            arr.append(name2)
            arr2.append(l)

# Find version specific info
if arr:
    k = arr[len(arr)-1]
    subprocess.call(('notify-send', '--icon', 'info', 'Update Available', 'Kernel %s is available' % k))
    url += arr2[len(arr2)-1]
    html = fetch_html(url)
    links = [] # reset
    p = LinkParser()
    p.feed(html)
    for l in links:
        # Format we want:
        # linux-headers-3.8.11-030811_3.8.11-030811.201305011408_all.deb
        if l.startswith('linux-headers') and l.endswith('all.deb'):
            # just the pertinent version info: 3.8.11-030811.201305011408
            name = l.split('_')[1]
            break
    a,b = name.rsplit('.', 1) # 3.8.11-030811, 201305011408
else:
    exit()

print '\nWHERE="%s"' % url
print 'VER_A="%s"' % a
print 'VER_B="%s"' % b
print 'VER_C="%s"' % uname.strip('-generic')
print '''\necho -e '\\nInformation:'
echo -e "\\tOrigin: \\n\\t\\t$WHERE\\n\\tKernel Version:\\n\\t\\t$VER_A"
echo -e "\\tRelease Date:\\n\\t\\t${VER_B:0:4}/${VER_B:4:2}/${VER_B:6:2} @ ${VER_B:8:2}:${VER_B:10:2} (YYYY/MM/DD @ HH:MM)\\n"

if [ "$1" == "--uninstall" ];then
	if [ "$VER_A" == "$VER_C" ];then
		echo -e "WARNING:\\n\\tYou are about to un-install the current running kernel,\\n\\tif you don't have a replacement kernel installed,\\n\\tyou will not be able to boot."
	fi
	if [ $(dpkg-query -l "linux-image-extra-$VER_A-generic" > /dev/null 2>&1;echo $?) -eq 0 ];then
		sudo apt-get purge linux-{image-extra,headers,image}-$VER_A-generic linux-headers-$VER_A
	else
		sudo apt-get purge linux-{headers,image}-$VER_A-generic linux-headers-$VER_A
	fi
	exit
elif [ "$1" == "--silent" ];then
	auto=1
else
	auto=0
fi
if [ "$1" == "--download-only" ];then
	download=1
else
	download=0
fi
if [ -n "$2" ];then
	if [ "$2" == "--download-only" ];then
		download=1
	elif [ "$2" == "--silent" ];then
		auto=1
	fi
fi

LOC="/tmp/kernel-$VER_A"
if [ -d "$LOC" ];then
	clear
	echo -e "Warning: This script has been run already\\nFiles are in $LOC\\nDelete existing downloads? (y=Yes, n=No) (y)"
	if [ $auto -eq 0 ];then
		read action
	else
		action="n"
	fi
	if [ ! "$action" == "n" ];then
		rm $LOC/* > /dev/null
	fi
else
	mkdir $LOC
fi
cd $LOC
arch=$(dpkg --print-architecture)
echo "Care to look at the change log? (y=Yes, n=No) (n)"
if [ $auto -eq 0 ];then
	read action
else
	action="n"
fi
if [ "$action" == "y" ];then
	curl $WHERE/CHANGES 2> /dev/null | less
	echo "Now that you read the change log, do you want to upgrade (y=Yes, n=No) (y)"
	read action
	if [ "$action" == "n" ];then
		exit
	fi
fi
wget -nc $WHERE/linux-headers-$VER_A"_$VER_A"."$VER_B"_all.deb
wget -nc $WHERE/linux-{image-extra,headers,image}-$VER_A-generic_$VER_A."$VER_B"_$arch.deb
clear
total=$(ls linux-*.deb | wc -l)
if [[ $total -eq 3 && ( $VER_B -gt 201304080035 || $VER_B -lt 201206041411 ) ]];then
	# Don't feel like inverting the above line and merging it with the line that is on this line plus two, so enjoy my sense of humor
	echo -e "Greetings $USER\\n  I ($(hostname)) am now self aware and a sentient being, have a nice day.\\n  Oh and by the way SKYNET is now active.\\n"
elif [ $total -ne 4 ];then
	echo -e "Failed to download all needed files\\nFiles are in $LOC\\nGet files from $WHERE\\n\\nThere should be 4 files, 3 ending with '$arch.deb' and 1 with 'all.deb'\\nHere is what we have:"
	ls $LOC
	echo -e "\\nYou can install what you have by running this command:\\n\\tsudo dpkg -i $LOC/linux-*.deb\\nJust be prepared for broken packages."
	exit 1
fi
if [ $download -eq 1 ];then
	echo -e "Packages have been downloaded to $LOC\\nHere is a list:"
	ls $LOC
	exit 0
fi
echo "Installing Linux $VER_A:"
sudo dpkg -i ./linux-*.deb
if [ -d /lib/modules/$VER_A-generic ];then
	echo -e "\\nThe New Kernel looks to have been installed"
	if [ $auto -eq 0 ] && [ "$VER_A" != "$VER_C" ];then
		echo -e "\\nWARNING: If the new kernel does not boot you may regret saying yes here.\\nWould you like to remove the current one? (y=Yes, n=No) (n)"
		read action
	else
		action="n"
	fi
	if [ "$action" == "y" ];then
		sudo apt-get purge linux-{image-extra,headers,image}-$VER_C-generic linux-headers-$VER_C
		if [ $(dpkg-query -l "linux-image-extra-$VER_C-generic" > /dev/null 2>&1;echo $?) -eq 0 ];then
			sudo apt-get purge linux-{image-extra,headers,image}-$VER_A-generic linux-headers-$VER_C
		else
			sudo apt-get purge linux-{headers,image}-$VER_C-generic linux-headers-$VER_C
		fi
	fi
else
	echo -e "Looks like the kernel was not installed for some reason\\nI don't see it in /lib/modules"
fi
echo -e "\\n\\nAre you ready to Reboot? (y=Yes, n=No) (n)"
if [ $auto -eq 0 ];then
	read action
else
	action="n"
fi
if [ "$action" == "y" ];then
	sudo reboot
fi
exit'''
