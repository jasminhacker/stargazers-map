#!/usr/bin/env python3

import argparse
import folium
import folium.plugins
import json
import requests
import shelve
import time
from bs4 import BeautifulSoup
from tqdm import tqdm

parser = argparse.ArgumentParser()
parser.add_argument(
    "stargazers", help="The file containing all users that should be visualized.",
)
args = parser.parse_args()

with open(args.stargazers) as f:
    stargazers = json.load(f)

# don't cluster too many markers together
cluster = folium.plugins.MarkerCluster(options={"maxClusterRadius": 40})
inf = float("Inf")
min_coord = [inf, inf]
max_coord = [-inf, -inf]

# fmt: off
def html_card(user):
    # returns an html popup for a given user
    return f"""
<div class="marker-popup">
  <img data-src="{user["avatar_url"]}" width="60" height="60">

  <div class="text">
    <div class="title">""" +\
    (f"""<span class="name">{user["name"]}</span>"""
    if user["name"] else "") +\
    f"""
      <a href="{user["html_url"]}" class="link">{user["login"]}</a>
    </div>""" +\
    (f"""
    <div>
      {user["bio"]}
    </div>"""
    if user["bio"] else "") +\
    f"""
    <div class="location">
      <i class="fas fa-map-marker-alt"></i>
      {user["location"]}
    </div>
  </div>
</div>
    """
# fmt: on


with shelve.open("locations.db") as db:
    for stargazer in tqdm(stargazers):
        stargazer_location = stargazer["location"]
        if stargazer_location is None:
            # if a user gave no location information they can't be visualized
            continue

        # look up the location in the local database
        if stargazer_location in db:
            location = db[stargazer_location]
        else:
            # perform a lookup on nominatim
            # take the most relevant (first) result
            params = {
                "q": stargazer_location,
                "format": "json",
                "limit": 1,
            }
            response = requests.get(
                "https://nominatim.openstreetmap.org/search", params=params
            )
            # respect the one request per second limit
            # https://operations.osmfoundation.org/policies/nominatim/
            time.sleep(1)
            try:
                location = response.json()[0]
            except IndexError:
                # location could not be found
                continue
            db[stargazer_location] = location

        # extend our bounding box if necessary
        coordinate = [float(location["lat"]), float(location["lon"])]
        min_coord[0] = min(min_coord[0], coordinate[0])
        min_coord[1] = min(min_coord[1], coordinate[1])
        max_coord[0] = max(max_coord[0], coordinate[0])
        max_coord[1] = max(max_coord[1], coordinate[1])

        # add a marker for the current user to the map
        folium.Marker(
            coordinate,
            icon=folium.Icon(prefix="fa", icon="circle", color="cadetblue"),
            popup=folium.Popup(html_card(stargazer), max_width="250"),
        ).add_to(cluster)

# create the map, fitted to show all markers
stargazers_map = folium.Map()
stargazers_map.fit_bounds([min_coord, max_coord])
stargazers_map.add_child(cluster)
stargazers_map.save("map.html")

# css for the popups (defined by the html above)
css = """
.marker-popup {
  font-family: Helvetica;
  display: flex;
}

.marker-popup img {
  float: left;
  border-radius: 3px;
  margin-right: 15px;
  display: inline-block;
}

.marker-popup .text {
  display: inline-block;
}
.marker-popup .title {
  margin-bottom: 4px;
}
.marker-popup .title span {
  margin-right: 3px;
}
.marker-popup .name {
  font-weight: bold;
}
.marker-popup .link {
  color: dimgrey;
}
.marker-popup .location {
  margin-top: 4px;
}
"""

# add the css by modifying the html file
with open("map.html") as f:
    soup = BeautifulSoup(f, "html.parser")
head = soup.head
head.append(soup.new_tag("style", type="text/css"))
head.style.append(css)
# find the name of the map variable
js_map = soup.select_one(".folium-map")["id"]
# so we can add an event listener to lazily load avatars.
soup.find_all("script")[-1].append(
    f"""
    {js_map}.on('popupopen', function(e) {{
        img = $(e.popup._content).find("img");
        img.attr("src", img.attr("data-src"));
    }});

"""
)
with open("map.html", "w") as f:
    f.write(str(soup))
