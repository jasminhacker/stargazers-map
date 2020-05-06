#!/usr/bin/env python3

import argparse
import json
import math
import os
import shelve
import time
from datetime import datetime
from github.GithubException import RateLimitExceededException
from github import Github
from tqdm import tqdm

parser = argparse.ArgumentParser()
parser.add_argument(
    "repository",
    help='The repository you want to analyze, e.g. "jonathanhacker/stargazers-map"',
)
args = parser.parse_args()

if "GITHUB_TOKEN" not in os.environ:
    print("using unauthenticated github api, rate limiting applies")
    print("to login with your account, run")
    print('`export GITHUB_TOKEN="<your OAuth-token>"`')
    print("get your token from https://github.com/settings/tokens/new")
    g = Github()
else:
    g = Github(os.environ["GITHUB_TOKEN"])

repo = g.get_repo(args.repository)
stargazers = repo.get_stargazers()

repository_basename = args.repository.split("/")[1]

stargazers_data = []

with shelve.open("stargazers.db") as db:
    for stargazer in tqdm(stargazers, total=stargazers.totalCount):

        while True:
            # in case of a ratelimit, repeat the request until successful
            try:
                # check if this user was already requested from the api
                stargazer_login = stargazer.login
                if stargazer_login in db:
                    stargazer_data = db[stargazer_login]
                else:
                    stargazer_data = {
                        "avatar_url": stargazer.avatar_url,
                        "bio": stargazer.bio,
                        "html_url": stargazer.html_url,
                        "login": stargazer.login,
                        "location": stargazer.location,
                        "name": stargazer.name,
                    }
                    db[stargazer_login] = stargazer_data
                stargazers_data.append(stargazer_data)
                # request was successful, break the endless loop and continue with the next user
                break
            except RateLimitExceededException:
                # check when the rate limit will be reset again and wait that long
                ratelimit_reset = g.get_rate_limit().core.reset
                left = ratelimit_reset - datetime.utcnow()
                seconds_waiting = math.ceil(left.total_seconds())
                print(f"rate limited, come back in {seconds_waiting/60:.2f} minutes")
                for _ in tqdm(range(seconds_waiting)):
                    time.sleep(1)

# write the collected data as a json to a file, saving the current one if it already exists
filename = repository_basename + "_stargazers.json"
if os.path.exists(filename):
    backup_filename = (
        repository_basename + "_stargazers_" + datetime.now().isoformat() + ".json"
    )
    print(f"{filename} already exists, moving it to {backup_filename}")
    os.rename(filename, backup_filename)

with open(filename, "w") as f:
    json.dump(stargazers_data, f)

print(f"stargazer information written to {filename}")
print(f"Visualize it with `./visualize.py {filename} && firefox map.html`")
