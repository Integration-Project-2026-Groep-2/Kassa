# Een centraal bestand voor instellingen zoals het IP-adres van de RabbitMQ server, gebruikersnamen en wachtwoorden.
"""Centrale configuratie-instellingen.

Plaats hier eenvoudige constants zoals hostnamen en queue-namen.
"""

# RabbitMQ host (pas aan naar uw omgeving)
RABBIT_HOST = 'localhost'

# Queue names — conform de formele contracten (zie Team Kassa contractoverzicht)
# Kassa publiceert op:
HEARTBEAT_QUEUE = 'kassa.heartbeat'
STATUS_QUEUE = 'kassa.status.checked'
PERSON_LOOKUP_QUEUE = 'kassa.person.lookup.requested'
PAYMENT_CONFIRMED_QUEUE = 'kassa.payment.confirmed'
UNPAID_REQUEST_QUEUE = 'kassa.unpaid.requested'
INVOICE_REQUESTED_QUEUE = 'kassa.invoice.requested'

# Kassa luistert op:
WARNING_QUEUE = 'controlroom.warning.issued'
PERSON_LOOKUP_RESPONSE_QUEUE = 'crm.person.lookup.responded'
USER_CONFIRMED_QUEUE = 'crm.user.confirmed'
COMPANY_CONFIRMED_QUEUE = 'crm.company.confirmed'
UNPAID_RESPONSE_QUEUE = 'crm.unpaid.responded'
USER_UPDATED_QUEUE = 'crm.user.updated'
COMPANY_UPDATED_QUEUE = 'crm.company.updated'
USER_DEACTIVATED_QUEUE = 'crm.user.deactivated'
COMPANY_DEACTIVATED_QUEUE = 'crm.company.deactivated'
#Een centraal bestand voor instellingen zoals het IP-adres van de RabbitMQ server, gebruikersnamen en wachtwoorden.