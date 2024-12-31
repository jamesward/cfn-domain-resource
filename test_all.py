import pytest
import index
from index import DomainManager, DomainManagerLive

class DomainManagerFake(DomainManager):
    events = []

    def list_operations(self, **kwargs):
        return {}

    def get_domain_detail(self, domain_name):
        return {
            'DomainName': domain_name
        }

    def get_operation_detail(self, operation_id):
        pass

    def list_domains(self, **kwargs):
        return {
            'Domains': [
                {
                    'DomainName': "foo.com"
                }
            ]
        }

    def check_domain_availability(self, **kwargs):
        pass

    def register_domain(self, **kwargs):
        self.events.append("register_domain")

    def update_domain_nameservers(self, **kwargs):
        pass

    def check_domain_transferability(self, **kwargs):
        pass

    def transfer_domain(self, **kwargs):
        self.events.append("transfer_domain")

def test_exists():

    event = {
        'ResourceProperties': {
            'DomainName': "foo.com",
            'Contact': {
                'firstName': "Joe",
                'lastName': "Bob",
                'type': "PERSON",
                'phoneNumber': "+1.3035551212",
                'email': "joe@bob.com",
                'addressLine1': "PO Box 123",
                'city': "Nowhere",
                'state': "CA",
                'countryCode': "US",
                'zipCode': "91222"
            },
            'AutoRenew':  True
        }
    }

    index.domain_manager = DomainManagerFake()

    response = index.create(event, None)
    assert response == "foo.com"
    assert len(index.domain_manager.events) == 0

def test_live_create_unavailable():
    event = {
        'ResourceProperties': {
            'DomainName': "foo.com",
            'Contact': {
                'firstName': "Joe",
                'lastName': "Bob",
                'type': "PERSON",
                'phoneNumber': "+1.3035551212",
                'email': "joe@bob.com",
                'addressLine1': "PO Box 123",
                'city': "Nowhere",
                'state': "CA",
                'countryCode': "US",
                'zipCode': "91222"
            },
            'AutoRenew':  True
        }
    }

    index.domain_manager = DomainManagerLive()

    with pytest.raises(Exception):
        index.create(event, None)

# def test_live_update():
#     event = {
#         'ResourceProperties': {
#             'DomainName': "armchairchats.com",
#             'Contact': {
#                 'firstName': "James",
#                 'lastName': "Ward",
#                 'type': "PERSON",
#                 'phoneNumber': "+1.3035551212",
#                 'email': "james@jamesward.com",
#                 'addressLine1': "PO Box 4202",
#                 'city': "Crested Butte",
#                 'state': "CO",
#                 'countryCode': "US",
#                 'zipCode': "81224"
#             },
#             'AutoRenew':  True,
#             'NameServers': [
#                 "ns1.afternic.com",
#                 "ns2.afternic.com",
#                 "verification-sixmy6f2sjew8cppecsorj.ns101.verify.hn"
#             ]
#         }
#     }
#
#     index.domain_manager = DomainManagerLive()
#     response = index.update(event, None)
#     print(response)
#     assert False
