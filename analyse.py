import statistics
import sys

file_name = sys.argv[1]

log_stat = {}
with open(file_name, "r") as log_file:
    for line in log_file:
        line = line.strip()
        log = line.split(":")
        if len(log) != 4 or log[0] != "INFO" or log[1] != "JupyterHubClient":
            continue
        call = log[2]
        res = log[3]
        if call not in log_stat:
            log_stat[call] = {"timeouts": 0, "durations": []}
        if res == "timeout":
            log_stat[call]["timeouts"] += 1
            continue
        log_stat[call]["durations"].append(float(res))

for call, stat in log_stat.items():
    mean = statistics.mean(stat["durations"])
    try:
        stdev = statistics.stdev(stat["durations"])
    except statistics.StatisticsError:
        stdev = -1
    msg = f"{call:>30} - MEAN: {mean:>6.2f}    STDEV: {stdev:>6.2f}"
    msg += f"    TIMEOUTS: {stat['timeouts']:>3}"
    print(msg)

