import sys; sys.path.insert(0, '.')
from traffic_quantum.hospital_maps import load_registered_drivers, authenticate_driver

drivers = load_registered_drivers()
for vnum, d in drivers.items():
    status = d.get('status', 'APPROVED')
    badge = 'APPROVED' if status == 'APPROVED' else 'PENDING APPROVAL'
    name = d['name']
    print(f'{vnum}: name={name} status={status} badge={badge}')

print()
for vnum in ['TN-09-EMS-108', 'TN-01-EMS-102']:
    ok, msg, _, jwt = authenticate_driver(vnum, '108080')
    print(f'{vnum}: ok={ok}, msg={msg!r}, JWT={jwt is not None}')
