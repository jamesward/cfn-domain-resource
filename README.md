# AWS CloudFormation Domain Resource

> [!IMPORTANT]
> **This repository is archived and replaced by [jamesward/cfn-extras-resource](https://github.com/jamesward/cfn-extras-resource).**
> Its **Domain** resource (`Handler: cfn_extras.domain.handler`) registers or transfers a Route 53 domain and keeps its contact, auto-renew and nameservers in sync. It ships with the other resources as one
> Lambda artifact in a public, versioned S3 bucket, so there's nothing to build. See that repository's
> README for the CloudFormation snippet and the per-release `S3ObjectVersion`.
>
> The original code and documentation below are kept for reference.

This project provides a custom CloudFormation resource for managing domain names and DNS records using AWS Route 53.

The AWS CloudFormation Domain Resource allows you to easily create and manage domain names and associated DNS records as part of your CloudFormation stacks. It simplifies the process of setting up and configuring domains for your applications deployed on AWS.

The Domain Resource supports the following operations:

- Create: Registers or transfers a domain
- Update: Updates existing DNS records for a domain

When deployed as a Lambda, Domains can be managed as custom resources, like:

```yaml
  DomainFunction:
     Type: AWS::Lambda::Function
     Properties:
        Code:
           S3Bucket:
              Ref: DomainBuildBucket
           S3Key: function.zip
        Handler: index.handler
        Role:
           Fn::GetAtt:
              - DomainRole
              - Arn
        Runtime: python3.9
        Timeout: 10

  foocomDomain:
    Type: AWS::CloudFormation::CustomResource
    Properties:
      ServiceTimeout: 70
      ServiceToken:
        Fn::GetAtt:
        - DomainFunction
        - Arn
      DomainName: foo.com
      Contact:
        firstName: Joe
        lastName: Bob
        type: PERSON
        addressLine1: PO Box 123
        city: Nowhere
        state: CA
        countryCode: US
        zipCode: 91234
        phoneNumber: '+1.8055551212'
        email: joe@bob.com
      NameServers:
        Fn::GetAtt:
        - foocomHostedZone
        - NameServers
      AutoRenew: true
```
