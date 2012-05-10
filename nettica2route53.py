#!/usr/bin/env python

"""

  Copy Domain/Zone from Nettica to Amazon Route53
 -------------------------------------------------
  Brian Parsons <brian@pmex.com>
  
  
  Requires: boto  - http://boto.cloudhackers.com/en/latest/index.html
            suds  - https://fedorahosted.org/suds/


  Variables:
 ------------

    awskeyid - Amazon AWS Credentials Security Key ID
    awskeysecret - Amazon AWS Secret that matches the security key id
    netticausername - Nettica Username
    netticapassword - Nettica Password
    defaultttl - the TTL to use in AWS Route 53
  
"""

## 
## CONFIGURATION VARIABLES
##

awskeyid = ''
awskeysecret = ''
netticausername = ''
netticapassword = ''

defaultttl = 60

# Libraries

import base64
import sys
from suds.client import Client
from boto.route53.connection import Route53Connection
from boto.route53.record import ResourceRecordSets
from boto.route53.exception import DNSServerError

# Get the domain name from the command line, print usage if not given

if len(sys.argv) < 2:
  print "Usage: %s <domainname>" % sys.argv[0]
  sys.exit(1)
else:
  zonename = sys.argv[1]
 
# Base64 encode password
b64password = base64.b64encode(netticapassword)

# Initialize Nettica
url = 'https://www.nettica.com/DNS/DnsApi.asmx?WSDL'
nettica = Client(url)

# Initialize the connection to AWS Route53
route53 = Route53Connection(awskeyid, awskeysecret)

# Logging for debug
#import logging
#logging.basicConfig(level=logging.INFO)
#logging.getLogger('suds.client').setLevel(logging.DEBUG)

try:
  (resultstatus,resultcount,netticarecords) = nettica.service.ListDomain(netticausername,b64password,zonename)
except ValueError:
  print "Unable to find domain %s in Nettica or credentials incorrect" % zonename
  sys.exit(1)
  
if resultstatus[1].Status != 200:
  sys.exit(1)
else:
  print "Found %s records for %s" % (resultcount[1], zonename)	

# Get the zoneid of the domain in AWS Route53 if it exists
try:
    route53zones = route53.get_all_hosted_zones()
except DNSServerError,  e:
    print 'Connection error to AWS. Check your credentials.'
    print 'Error %s - %s' % (e.code,  str(e))
    sys.exit(1)

for zone in route53zones['ListHostedZonesResponse']['HostedZones']:
    if zone['Name'][0:-1] in zonename:
        zoneid = zone['Id'].replace('/hostedzone/', '')
        print 'Found Route53 Zone %s for %s' % (zoneid,  zonename)

# If we didn't find a zoneid, create it. 
try:
    zoneid
except NameError:
    print 'Unable to find Route53 Zone for %s. Creating...' % zonename
    try: 
        newzone = route53.create_hosted_zone(zonename, comment='imported from Nettica')
    except DNSServerError,  e:
	print 'Connection error to AWS. Check your credentials.'
	print 'Error %s - %s' % (e.code,  str(e))
	sys.exit(1)
    info = newzone['CreateHostedZoneResponse']
    nameservers = ', '.join(info['DelegationSet']['NameServers'])
    zoneid = info['HostedZone']['Id'].replace('/hostedzone/', '')
    print "Created Zone %s for %s" % (zoneid, zonename)
    print "Name Servers: %s" % nameservers
    
# Add the records to AWS Route53

# First get a list of existing records
try:
    sets = route53.get_all_rrsets(zoneid)
except DNSServerError,  e:
    print 'Connection error to AWS.'
    print 'Error %s - %s' % (e.code,  str(e))
    sys.exit(1)

mxrecord=[]
for netticarecord in netticarecords[1].DomainRecord:
  # Can't do F, NS or SOA records
  if netticarecord.RecordType == 'NS':
    print "Skipping NS Record.."
    continue
  if netticarecord.RecordType == 'SOA':
    print "Skipping SOA Record.."
    continue  
  if netticarecord.RecordType == 'F':
      print "Skipping F Record %s > %s..." % (netticarecord.HostName,  netticarecord.Data)
      continue
  # Adjust Data for MX Records
  if netticarecord.RecordType == 'MX':
      foundmx=1
      print "Found an MX record. Saving it for later..."
      mxrecord.append(str(netticarecord.Priority) + " " + netticarecord.Data)
      continue
  if netticarecord.HostName == None:
        newhostname=zonename
  else:
        newhostname=netticarecord.HostName + "." + zonename
  # Add trailing dot to hostname if it doesn't have one
  if newhostname[-1:] != ".":
        newhostname += "."    
  print ">> %s %s %s " % (newhostname, netticarecord.RecordType, netticarecord.Data)
  # Find the old record if it exists
  foundoldrecord = 0
  for rset in sets:
    if rset.name == newhostname and rset.type == netticarecord.RecordType:
        curdatarecord = rset.resource_records
        if type(curdatarecord) in [list, tuple, set]:
            for record in curdatarecord:
                curdata = record
        print 'Current data found for %s: %s' % (newhostname, curdata)
        curttl = rset.ttl
        print 'Current DNS TTL: %s' % curttl
  
        if curdata != netticarecord.Data:
            # Remove the old record
            print 'Removing old record...'
            change1 = ResourceRecordSets(route53, zoneid)
            removeold = change1.add_change("DELETE", newhostname, netticarecord.RecordType, curttl)
            removeold.add_value(curdata)
            change1.commit()
        
        else:
            print 'Data matches,  not making any changes in AWS Route53.'
            foundoldrecord = 1

  if foundoldrecord == 0:
      print 'Adding %s to AWS Route53 as %s %s...' % ( newhostname, netticarecord.RecordType, netticarecord.Data )
      change2 = ResourceRecordSets(route53, zoneid)
      change = change2.add_change("CREATE", newhostname, netticarecord.RecordType, defaultttl)
      change.add_value(netticarecord.Data)
      change2.commit()
      
if foundmx == 1:
        print "Processing MX records..."
        print "Looking for MX records in Route53..."
        foundawsmx = 0
        for rset in sets:
            if rset.type == 'MX':
                awsmxrecords = rset.resource_records
                foundawsmx = 1
        if foundawsmx == 1:
            print "Removing AWS current MX records..."
            change4 = ResourceRecordSets(route53, zoneid)
            change = change4.add_change("DELETE",  zonename + ".",  'MX',  defaultttl)
            for mxserver in awsmxrecords:
                change.add_value(mxserver)
            change4.commit()
        print "Adding MX records for %s:" % (zonename)
        change3 = ResourceRecordSets(route53, zoneid)
        change = change3.add_change("CREATE",  zonename + ".",  'MX',  defaultttl)
        for mxserver in mxrecord:
            print mxserver
            change.add_value(mxserver)
        change3.commit()
        
zonedata = route53.get_hosted_zone(zoneid)
nameservers = zonedata['GetHostedZoneResponse']['DelegationSet']['NameServers']
print "----------------------------------------------------------------------------"
print "Zone Processing Completed. AWS Route 53 Name Servers for %s:" % (zonename)
for server in nameservers:
    print "    %s" % server
    
