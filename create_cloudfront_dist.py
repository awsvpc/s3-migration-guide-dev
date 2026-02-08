import boto3
import uuid
cf = boto3.client('cloudfront')

customer_name = "geroge.hello.io"

s3_bucket = ".s3-website-us-east-1.amazonaws.com"

caller_reference_uuid = "%s" % (uuid.uuid4())

response = cf.create_distribution(DistributionConfig=dict(CallerReference=caller_reference_uuid,
            Aliases = dict(Quantity=1, Items=[customer_name]),
            DefaultRootObject='index.html',
            Comment='{0}'.format(customer_name),
            Enabled=True,
            PriceClass = 'PriceClass_100',
            Origins = dict(
                Quantity = 1, 
                Items = [dict(
                    Id = '1',
                    DomainName='{0}{1}'.format(customer_name,s3_bucket),
                    CustomOriginConfig = dict(HTTPPort = 80,HTTPSPort = 443,OriginProtocolPolicy = "https-only" )
                    )
                ]),
            ViewerCertificate = dict(
            CloudFrontDefaultCertificate = False,
            SSLSupportMethod =  'sni-only',
            Certificate = 'arn:aws:acm:us-east-1:637624592309:certificate/75ac2b7c-cb18-49e3-99c4-5cab8fb65268',
            CertificateSource = 'acm'
            ),
            
                DefaultCacheBehavior = dict(
                TargetOriginId = '1',
                ViewerProtocolPolicy= 'redirect-to-https',
                TrustedSigners = dict(Quantity=0, Enabled=False),
                ForwardedValues=dict(
                    Cookies = {'Forward':'all'},
                    Headers = dict(Quantity=0),
                    QueryString=False,
                    QueryStringCacheKeys= dict(Quantity=0),
                    ),
                MinTTL=1000)
            )
)

# Get the newly created clodufront to pass to Route53
route53_domain_name = response["Distribution"]["DomainName"]
