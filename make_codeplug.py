#!/usr/bin/env python3
import json
import yaml
import sys

from decimal import Decimal


def dedupe_name(zone, group, channels):
    name = f"{zone} {group}"

    if len(name) > 16:
        zone = zone.split()[0]
        name = f"{zone} {group}"

    if len(name) > 16:
        short_group = group[:16-len(zone)]

        name = f"{zone} {short_group}"

    if len(name) > 16:
        short_zone = zone[:8]
        short_group = group[:8]

        name = f"{short_zone}{short_group}"

    if len(name) > 16:
        # Screw it
        name = name[:16]

    channel_names = set([c["Name"] for c in channels])

    num = 1
    while name in channel_names:
        num += 1
        str_num = str(num)
        name = name[:-len(str_num)] + str_num

    return name


def main(codeplug_file, repeater_file, output):
    codeplug = {}
    groups = {}
    groupsets = {}
    repeaters = {}
    dmr_base = {}
    analog_base = {}

    with open(codeplug_file) as f:
        codeplug = json.load(f)

    with open(repeater_file) as f:
        data = yaml.load(f)

        groups = data.get("groups", {})
        groupsets = data.get("groupsets", {})
        repeaters = data.get("repeaters", {})
        dmr_base = data.get("Digital Base Channel", {})
        analog_base = data.get("Analog Base Channel", {})

    missing_groups = dict(groups)

    for contact in codeplug["Contacts"]:
        num_id = int(contact["CallID"])
        names = [name for name, id in missing_groups.items() if int(id) == num_id]

        if names:
            # We already have this item in the list, so make sure its name matches
            assert len(names[0]) <= 16
            contact["Name"] = names[0]
            for name in names:
                missing_groups.pop(name)

        # Otherwise we can just leave it alone so we don't clobber real contacts

    # Now take care of all the normal ones
    for group, id in missing_groups.items():
        assert len(group) <= 16
        codeplug["Contacts"].append({
            "CallID": str(id),
            "CallReceiveTone": "No",
            "CallType": "Group",
            "Name": group,
        })

    # Any zones we don't know about
    extra_zones = [zone for zone in codeplug["Zones"] if zone["Name"] not in repeaters]
    all_channels = []

    for zone in extra_zones:
        for name in zone.get("Channel", []):
            chan_infos = [chan for chan in codeplug.get("Channels", []) if chan["Name"] == name]
            all_channels.extend(chan_infos)

    for name, info in repeaters.items():
        assert len(name) <= 16
        zone = {
            "Channel": [],
            "Name": name,
        }

        groupset = info.get("groupset", None)
        if groupset:
            groups = groupsets[groupset]

            for group in groups:
                chan_name = dedupe_name(zone["Name"], group, all_channels)
                zone["Channel"].append(chan_name)

                chan_info = dict(dmr_base)

                tx_freq = Decimal(info["frequency"])
                rx_freq = tx_freq + Decimal(info["offset"])

                assert len(chan_name) <= 16

                chan_info.update({
                    "ContactName": group,
                    "Name": chan_name,
                    "TxFrequency": f"{tx_freq:03.5f}",
                    "RxFrequency": f"{rx_freq:03.5f}",
                    "ColorCode": str(info["color"]),
                })

                all_channels.append(chan_info)
            assert len(zone["Channel"]) <= 16

        extra_zones.append(zone)

    codeplug["Zones"] = extra_zones
    codeplug["Channels"] = all_channels

    with open(output, "w") as f:
        json.dump(codeplug, f)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <codeplug file.json> <repeater file.json> [output_file]")
        exit(0)

    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) >= 3 else 'output.json')
