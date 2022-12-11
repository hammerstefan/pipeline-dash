# type: ignore
# file currently unused
import os
import pickle
from urllib.parse import urlparse

import requests
import yaml
from bs4 import BeautifulSoup


def init_session(session, servers, user_file):
    if os.path.exists(".cookies"):
        with open(".cookies", "rb") as f:
            session.cookies.update(pickle.load(f))
    for server in servers:
        authenticate(session, server, user_file)


def save_cookies(session):
    with open(".cookies", "wb") as f:
        pickle.dump(session.cookies, f)


def authenticate(session: requests.Session, url: str, user_file: str) -> requests.Session:
    # Ubuntu SSO authentication hack
    # Should not be required anymore
    sess = session
    req = sess.get(url)
    if req.url == url or req.url == f"{url}/":
        return session
    req = sess.post(req.url, data={"openid_identifier": "login.ubuntu.com"})

    soup = BeautifulSoup(req.text, "html.parser")
    s2 = soup.find(id="openid_message")
    url2 = s2.attrs["action"]
    data = {i.attrs["name"]: i.attrs["value"] for i in s2.find_all("input", attrs={"name": True})}
    req2 = sess.post(url2, data)
    if req2.url == url or req2.url == f"{url}/":
        return session
    soup = BeautifulSoup(req2.text, "html.parser")
    s2 = soup.find("form", id="login-form")
    url = "https://" + urlparse(req2.url).netloc + s2.attrs["action"]
    data = {
        i.attrs["name"]: i.attrs["value"] if "value" in i.attrs else ""
        for i in s2.find_all("input", attrs={"name": True})
    }
    data2 = {}
    for key in ["csrfmiddlewaretoken", "user-intentions", "openid.usernamesecret"]:
        data2[key] = data[key]
    with open(user_file) as file:
        user_data = yaml.safe_load(file)
    data2["email"] = user_data["email"]
    data2["password"] = user_data["password"]
    data2["continue"] = ""
    req3 = sess.post(
        url,
        data2,
        headers={
            "Referer": url,
        },
    )
    token = input("2FA Token: ")
    data4 = {}
    soup = BeautifulSoup(req3.text, "html.parser")
    s3 = soup.find("form", id="login-form")
    data = {
        i.attrs["name"]: i.attrs["value"] if "value" in i.attrs else ""
        for i in s3.find_all("input", attrs={"name": True})
    }
    for key in ["csrfmiddlewaretoken", "openid.usernamesecret"]:
        data4[key] = data[key]
    data4["continue"] = ""
    data4["oath_token"] = token
    req4 = sess.post(
        req3.url,
        data4,
        headers={
            "Referer": req3.url,
        },
    )

    if "device-verify" in req4.url:
        soup = BeautifulSoup(req4.text, "html.parser")
        s4 = soup.find("form", id="login-form")
        data = {
            i.attrs["name"]: i.attrs["value"] if "value" in i.attrs else ""
            for i in s4.find_all("input", attrs={"name": True})
        }
        data5 = {}
        for key in ["csrfmiddlewaretoken", "openid.usernamesecret"]:
            data5[key] = data[key]
        data5["continue"] = ""
        req5 = sess.post(
            req4.url,
            data5,
            headers={
                "Referer": req4.url,
            },
        )
    return sess
