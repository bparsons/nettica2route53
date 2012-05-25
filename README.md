# Copy Domain/Zone from Nettica to Amazon Route53

This python script will copy the DNS records for a domain from Nettica to Amazon Route 53.   

You'll need boto and suds python libraries.   
  
## Requires: 

* boto - http://boto.cloudhackers.com/en/latest/index.html
* suds - https://fedorahosted.org/suds/

##  Variables
 
* awskeyid - Amazon AWS Credentials Security Key ID
* awskeysecret - Amazon AWS Secret that matches the security key id
* netticausername - Nettica Username
* netticapassword - Nettica Password
* defaultttl - the TTL to use in AWS Route 53

## Usage

You need to edit the script to place your AWS and Nettica credentials in the variables near the top of the script. Then it's ready to go:

    nettica2route53.py <domainname> 

