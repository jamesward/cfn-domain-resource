from __future__ import print_function

from abc import abstractmethod, ABC
from dataclasses import dataclass

from crhelper import CfnResource
import logging
import boto3

from typing import Optional, List

logger = logging.getLogger(__name__)

helper = CfnResource(json_logging=False, log_level='DEBUG', boto_level='CRITICAL', sleep_on_delete=120, ssl_verify=None)

class DomainManager(ABC):
    @abstractmethod
    def list_domains(self) -> dict:
        pass

    @abstractmethod
    def list_operations(self, **kwargs) -> dict:
        pass

    @abstractmethod
    def get_domain_detail(self, domain_name) -> dict:
        pass

    @abstractmethod
    def get_operation_detail(self, operation_id) -> dict:
        pass

    def get_domain(self, domain_name) -> Optional[dict]:
        domains_response = self.list_domains()
        print(domains_response)

        for domain in domains_response['Domains']:
            if domain['DomainName'] == domain_name:
                return self.get_domain_detail(domain_name)

        operations_response = self.list_operations()

        for operation in operations_response['Operations']:
            if (operation['Status'] == 'IN_PROGRESS' and
                operation['Type'] == 'DOMAIN_TRANSFER_IN' and
                operation['DomainName'] == domain_name):
                return self.get_operation_detail(operation['OperationId'])

        return None

    @abstractmethod
    def check_domain_availability(self, domain_name) -> dict:
        pass

    @abstractmethod
    def register_domain(self, **kwargs) -> dict:
        pass

    @abstractmethod
    def update_domain_nameservers(self, **kwargs) -> dict:
        pass

    @abstractmethod
    def check_domain_transferability(self, **kwargs) -> dict:
        pass

    @abstractmethod
    def transfer_domain(self, **kwargs) -> dict:
        pass

class DomainManagerLive(DomainManager):

    def __init__(self):
        self.client = boto3.client('route53domains')

    def list_domains(self) -> dict:
        return self.client.list_domains()

    def list_operations(self, **kwargs) -> dict:
        return self.client.list_operations(**kwargs)

    def get_domain_detail(self, domain_name) -> dict:
        return self.client.get_domain_detail(DomainName = domain_name)

    def get_operation_detail(self, operation_id) -> dict:
        return self.client.get_operation_detail(OperationId = operation_id)

    def check_domain_availability(self, domain_name) -> dict:
        return self.client.check_domain_availability(DomainName = domain_name)

    def register_domain(self, **kwargs) -> dict:
        return self.client.register_domain(**kwargs)

    def update_domain_nameservers(self, **kwargs) -> dict:
        return self.client.update_domain_nameservers(**kwargs)

    def check_domain_transferability(self, **kwargs) -> dict:
        return self.client.check_domain_transferability(**kwargs)

    def transfer_domain(self, **kwargs) -> dict:
        return self.client.transfer_domain(**kwargs)

@dataclass
class Contact:
    first_name: str
    last_name: str
    contact_type: str
    address_line_1: str
    city: str
    state: str
    country_code: str
    zip_code: str
    phone_number: str
    email: str


@dataclass
class DomainEvent:
    domain_name: str
    contact: Contact
    auto_renew: bool
    name_servers: Optional[List[str]]


try:
    domain_manager = DomainManagerLive()
    pass
except Exception as e:
    helper.init_failure(e)


def parse_event(event):
    return DomainEvent(
        domain_name=event['ResourceProperties']['DomainName'],
        contact=Contact(
            first_name=event['ResourceProperties']['Contact']['firstName'],
            last_name=event['ResourceProperties']['Contact']['lastName'],
            contact_type=event['ResourceProperties']['Contact'].get('type'),
            address_line_1=event['ResourceProperties']['Contact']['addressLine1'],
            city=event['ResourceProperties']['Contact']['city'],
            state=event['ResourceProperties']['Contact']['state'],
            country_code=event['ResourceProperties']['Contact']['countryCode'],
            zip_code=event['ResourceProperties']['Contact']['zipCode'],
            phone_number=event['ResourceProperties']['Contact']['phoneNumber'],
            email=event['ResourceProperties']['Contact']['email']
        ),
        auto_renew=event['ResourceProperties']['AutoRenew'],
        name_servers=event['ResourceProperties'].get('NameServers', [])
    )


@helper.create
def create(event, context):
    logger.info("Got Create")
    domain_event = parse_event(event)
    domain = domain_manager.get_domain(domain_event.domain_name)

    if domain is None:
        transfer_auth_code = event['ResourceProperties'].get('TransferAuthCode')

        if transfer_auth_code is None:
            availability = domain_manager.check_domain_availability(domain_event.domain_name)

            if availability['Availability'] == 'AVAILABLE':
                domain_manager.register_domain(
                    DomainName = domain_event.domain_name,
                    DurationInYears = 1,
                    AutoRenew = domain_event.auto_renew,
                    AdminContact = domain_event.contact,
                    RegistrantContact = domain_event.contact,
                    TechContact = domain_event.contact,
                    PrivacyProtectAdminContact = True,
                    PrivacyProtectRegistrantContact = True,
                    PrivacyProtectTechContact = True
                )

                if domain_event.name_servers:
                    domain_manager.update_domain_nameservers(
                        DomainName = domain_event.domain_name,
                        Nameservers = [{'Name': ns} for ns in domain_event.name_servers]
                    )
            else:
                raise Exception(f"Domain {domain_event.domain_name} is not available")
        else:
            transferability = domain_manager.check_domain_transferability(
                DomainName = domain_event.domain_name,
                AuthCode = transfer_auth_code
            )

            if transferability['Transferability']['Transferable'] == 'TRANSFERABLE':
                params = {
                    'DomainName': domain_event.domain_name,
                    'AuthCode': transfer_auth_code,
                    'DurationInYears': 1,
                    'AutoRenew': domain_event.auto_renew,
                    'AdminContact': domain_event.contact,
                    'RegistrantContact': domain_event.contact,
                    'TechContact': domain_event.contact,
                    'PrivacyProtectAdminContact': True,
                    'PrivacyProtectRegistrantContact': True,
                    'PrivacyProtectTechContact': True
                }

                if domain_event.name_servers:
                    params['Nameservers'] = [{'Name': ns} for ns in domain_event.name_servers]

                domain_manager.transfer_domain(**params)
            else:
                raise Exception(f"Domain {domain_event.domain_name} is not transferable")

    return domain_event.domain_name


@helper.update
def update(event, context):
    logger.info("Got Update")
    domain_event = parse_event(event)
    domain = domain_manager.get_domain(domain_event.domain_name)

    if domain is None:
        raise Exception(f"Domain {domain_event.domain_name} does not exist")
    else:
        # todo: update domain
        pass

    return domain_event.domain_name

    # domain_details = client.get_domain_detail(
    #     DomainName = domain_name(event)
    # )
    #
    # status = domain_details.get('StatusList', [])
    # pending_transfer = any('PENDING_TRANSFER' in s for s in status)
    #
    # def contacts_are_different(new_contact, old_contact):
    #
    #     print(f"New: {str(new_contact)}")
    #     print(f"Old: {str(old_contact)}")
    #
    #     fields_to_compare = [
    #         'FirstName',
    #         'LastName',
    #         'ContactType',
    #         'OrganizationName',
    #         'AddressLine1',
    #         'AddressLine2',
    #         'City',
    #         'State',
    #         'CountryCode',
    #         'ZipCode',
    #         'PhoneNumber',
    #         'Email'
    #     ]
    #
    #     for field in fields_to_compare:
    #         if old_contact.get(field) != new_contact.get(field):
    #             return True
    #
    #     return False
    #
    # if not pending_transfer:
    #     updated_admin_contact = contacts_are_different(contact(event), domain_details.get('AdminContact', {}))
    #     updated_registrant_contact = contacts_are_different(contact(event), domain_details.get('RegistrantContact', {}))
    #     updated_tech_contact = contacts_are_different(contact(event), domain_details.get('TechContact', {}))
    #
    #     if updated_admin_contact or updated_registrant_contact or updated_tech_contact:
    #         client.update_domain_contact(
    #             DomainName = domain_name(event),
    #             AdminContact = contact(event),
    #             RegistrantContact = contact(event),
    #             TechContact = contact(event)
    #         )
    #
    #     # todo: update autoRenew
    #
    #     # todo: if updated
    #     if name_servers(event):
    #         client.update_domain_nameservers(
    #             DomainName = domain_name(event),
    #             Nameservers = name_servers(event)
    #         )


@helper.delete
def delete(event, context):
    logger.info("Got Delete")

    # client.get_domain_detail(
    #     DomainName = domain_name
    # )

    # How do we handle Delete? What about rollbacks? What about moving from one CFN to another? Maybe a field that confirms we actually want to delete it?
    # client.delete_domain(
    #  DomainName = domain_name
    # )


def handler(event, context):
    helper(event, context)
