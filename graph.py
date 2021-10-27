import os
import sys
import pathlib
import re
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator


def main():
    try:
        log_file = pathlib.Path(sys.argv[1])
    except IndexError:
        print("Need to specify file")
        sys.exit(1)

    if not log_file.exists():
        print(f"{log_file} does not exists")
        sys.exit(1)

    lines = []
    timeouts = []
    total_timeouts = 0
    # read log file
    with log_file.open(mode="r", encoding="utf-8") as log_file_df:
        for line in log_file_df.readlines():
            users = re.match("^Testing ([0-9]+) users", line)
            login = re.match("\W+login - MEAN:\W*([0-9\.]+)\W+STDEV:.*", line)
            if users:
                timeouts.append(total_timeouts)
                lines.append(users.group(1))
                total_timeouts = 0
            if login:
                lines.append(login.group(1))
            tmp = re.match(".*STDEV:\W+[0-9\.]+\W+TIMEOUTS:\W+([0-9]+)", line)
            if tmp:
                total_timeouts += int(tmp.group(1))


    # 0,3,6,9,... are amount of users
    nusers = list(map(int,lines[::3]))
    # 1,4,7,10,... are initial login time
    login_init = list(map(float,lines[1::3]))
    # 2,5,8,11,... time to login to existing sessions
    login_existing = list(map(float,lines[2::3]))

    n_samples = min(len(nusers), len(login_init), len(login_init), len(timeouts)) - 1

    fig, [ax1, ax2] = plt.subplots(
        nrows=2, ncols=1, figsize=(16,9), gridspec_kw={'height_ratios': [2, 1]}
    )
    ax1.plot(nusers[:n_samples], login_init[:n_samples], label="New session")
    ax1.plot(nusers[:n_samples], login_existing[:n_samples], label="Existing session")
    ax1.set(ylabel='Login time (second)')
    ax1.grid()
    ax1.legend()

    ax2.plot(nusers[:n_samples], timeouts[:n_samples], label="Timeouts")
    ax2.set(xlabel='Number of users', ylabel="Timeouts")
    ax2.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax2.grid()

    if bool(os.environ.get('DISPLAY')):
        plt.show()
    else:
        file_name = "benchmark.png"
        print(f"Saving result to {file_name}")
        fig.savefig(file_name)

if __name__ == "__main__":
    main()
