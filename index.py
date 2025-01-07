from __future__ import print_function

from abc import abstractmethod, ABC
from dataclasses import dataclass

from crhelper import CfnResource
import logging
import boto3

from typing import Optional, List

logger = logging.getLogger(__name__)

helper = CfnResource(json_logging=False, log_level='DEBUG', boto_level='CRITICAL', sleep_on_delete=120, ssl_verify=None)


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

    def to_boto(self):
        return {
            'FirstName': self.first_name,
            'LastName': self.last_name,
            'ContactType': self.contact_type,
            'AddressLine1': self.address_line_1,
            'City': self.city,
            'State': self.state,
            'CountryCode': self.country_code,
            'ZipCode': self.zip_code,
            'PhoneNumber': self.phone_number,
            'Email': self.email
        }

@dataclass
class DomainEvent:
    domain_name: str
    contact: Contact
    auto_renew: bool
    name_servers: Optional[List[str]]


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

    def get_domain_or_operation(self, domain_name) -> Optional[dict | str]:
        domains_response = self.list_domains()

        for domain in domains_response['Domains']:
            if domain['DomainName'] == domain_name:
                return self.get_domain_detail(domain_name)

        operations_response = self.list_operations()

        for operation in operations_response['Operations']:
            if (operation['Status'] == 'IN_PROGRESS' and
                operation['Type'] == 'TRANSFER_IN_DOMAIN' and
                operation['DomainName'] == domain_name):
                return operation['OperationId']

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

    def update_domain_nameservers(self, domain_name: str, name_servers: List[str]) -> dict:
        return self.client.update_domain_nameservers(
            DomainName = domain_name,
            Nameservers = [{'Name': ns} for ns in name_servers]
        )

    def check_domain_transferability(self, **kwargs) -> dict:
        return self.client.check_domain_transferability(**kwargs)

    def transfer_domain(self, **kwargs) -> dict:
        return self.client.transfer_domain(**kwargs)

    def update_domain_contact(self, domain_name: str, contact: Contact):
        updated_contact = contact.to_boto()

        return self.client.update_domain_contact(
            DomainName = domain_name,
            AdminContact = updated_contact,
            RegistrantContact = updated_contact,
            TechContact = updated_contact
        )

    def enable_domain_auto_renew(self, domain_name: str):
        return self.client.enable_domain_auto_renew(DomainName = domain_name)

    def disable_domain_auto_renew(self, domain_name: str):
        return self.client.disable_domain_auto_renew(DomainName = domain_name)


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
        auto_renew=bool(event['ResourceProperties'].get('AutoRenew', True)),
        name_servers=event['ResourceProperties'].get('NameServers', [])
    )

def contacts_are_equal(new_contact: dict, old_contact: Contact):
    return (
            new_contact.get("FirstName") == old_contact.first_name and
            new_contact.get("LastName") == old_contact.last_name and
            new_contact.get("ContactType") == old_contact.contact_type and
            new_contact.get("AddressLine1") == old_contact.address_line_1 and
            new_contact.get("City") == old_contact.city and
            new_contact.get("State") == old_contact.state and
            new_contact.get("CountryCode") == old_contact.country_code and
            new_contact.get("ZipCode") == old_contact.zip_code and
            new_contact.get("PhoneNumber") == old_contact.phone_number and
            new_contact.get("Email") == old_contact.email
    )

def nameservers_are_equal(new_name_servers: List[str], old_name_servers: List[str]):
    return set(new_name_servers) == set(old_name_servers)

# todo: create should not try to transfer domains already being transferred
# todo: create & update should do the same things?

@helper.create
@helper.update
def create_or_update(event, context):
    domain_event = parse_event(event)
    domain_or_operation = domain_manager.get_domain_or_operation(domain_event.domain_name)

    if domain_or_operation is None:
        transfer_auth_code = event['ResourceProperties'].get('TransferAuthCode')

        if transfer_auth_code is None:
            availability = domain_manager.check_domain_availability(domain_event.domain_name)

            if availability['Availability'] == 'AVAILABLE':
                domain_manager.register_domain(
                    DomainName = domain_event.domain_name,
                    DurationInYears = 1,
                    AutoRenew = domain_event.auto_renew,
                    AdminContact = domain_event.contact.to_boto(),
                    RegistrantContact = domain_event.contact.to_boto(),
                    TechContact = domain_event.contact.to_boto(),
                    PrivacyProtectAdminContact = True,
                    PrivacyProtectRegistrantContact = True,
                    PrivacyProtectTechContact = True
                )

                if domain_event.name_servers:
                    domain_manager.update_domain_nameservers(domain_event.domain_name, domain_event.name_servers)
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
                    'AdminContact': domain_event.contact.to_boto(),
                    'RegistrantContact': domain_event.contact.to_boto(),
                    'TechContact': domain_event.contact.to_boto(),
                    'PrivacyProtectAdminContact': True,
                    'PrivacyProtectRegistrantContact': True,
                    'PrivacyProtectTechContact': True
                }

                if domain_event.name_servers:
                    params['Nameservers'] = [{'Name': ns} for ns in domain_event.name_servers]

                domain_manager.transfer_domain(**params)
            else:
                raise Exception(f"Domain {domain_event.domain_name} is not transferable")
    elif isinstance(domain_or_operation, str):
        # pending transfer
        pass
    else:
        admin_contact_same = contacts_are_equal(domain_or_operation.get('AdminContact', {}), domain_event.contact)
        registrant_contact_same = contacts_are_equal(domain_or_operation.get('RegistrantContact', {}), domain_event.contact)
        tech_contact_same = contacts_are_equal(domain_or_operation.get('TechContact', {}), domain_event.contact)

        if not admin_contact_same or not registrant_contact_same or not tech_contact_same:
            domain_manager.update_domain_contact(domain_event.domain_name, domain_event.contact)


        if domain_event.auto_renew != domain_or_operation.get('AutoRenew', False):
            if domain_event.auto_renew:
                domain_manager.enable_domain_auto_renew(domain_event.domain_name)
            else:
                domain_manager.disable_domain_auto_renew(domain_event.domain_name)


        if domain_event.name_servers:
            old_nameservers = [ns.get('Name') for ns in domain_or_operation.get('Nameservers', [])]
            nameservers_same = nameservers_are_equal(domain_event.name_servers, old_nameservers)
            if not nameservers_same:
                domain_manager.update_domain_nameservers(domain_event.domain_name, domain_event.name_servers)

    return domain_event.domain_name


def handler(event, context):
    helper(event, context)
