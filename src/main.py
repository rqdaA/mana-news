import html
import os
import re
import traceback
import urllib.parse

import discord
import requests

UA = "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/116.0"
MANADA_URL = os.environ.get("MANADA_URL")
MANADA_USER = os.environ.get("MANADA_USER")
MANADA_PWD = os.environ.get("MANADA_PWD")
AUTH_URL = os.environ.get("AUTH_URL")
TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL = os.environ.get("CHANNEL", "")
NOTICE_URL = os.environ.get("NOTICE_URL", "")

if not all(
        [e for e in (TOKEN, CHANNEL, MANADA_USER, MANADA_PWD, AUTH_URL, MANADA_URL, NOTICE_URL)]
):
    print("Not all variables are set")
    exit(1)


def get_shib() -> dict[str, str]:
    s = requests.session()

    headers = {
        "User-Agent": UA,
    }

    r = s.get(f"{MANADA_URL}/ct/home", headers=headers)

    headers = {
        "User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = {
        "shib_idp_ls_exception.shib_idp_session_ss": "",
        "shib_idp_ls_success.shib_idp_session_ss": "true",
        "shib_idp_ls_value.shib_idp_session_ss": "",
        "shib_idp_ls_exception.shib_idp_persistent_ss": "",
        "shib_idp_ls_success.shib_idp_persistent_ss": "true",
        "shib_idp_ls_value.shib_idp_persistent_ss": "",
        "shib_idp_ls_supported": "true",
        "_eventId_proceed": "",
    }

    r = s.post(
        f"{AUTH_URL}?execution=e1s1",
        headers=headers,
        data=data,
    )

    ######

    data = {
        "j_username": MANADA_USER,
        "j_password": MANADA_PWD,
        "_eventId_proceed": "",
    }

    r = s.post(
        f"{AUTH_URL}?execution=e1s2",
        headers=headers,
        data=data,
    )

    ######

    data = {
        "shib_idp_ls_exception.shib_idp_session_ss": "",
        "shib_idp_ls_success.shib_idp_session_ss": "true",
        "_eventId_proceed": "",
    }

    r = s.post(
        f"{AUTH_URL}?execution=e1s3",
        headers=headers,
        data=data,
    )

    relay_state, saml = map(lambda x: x[7:-3], re.findall(r'value=".*"/>', r.text)[:2])

    ######

    data = {"RelayState": html.unescape(relay_state), "SAMLResponse": saml}

    r = s.post(
        f"{MANADA_URL}/Shibboleth.sso/SAML2/POST",
        headers=headers,
        data=data,
    )
    shib_key = [
        k for k in s.cookies.get_dict().keys() if k.startswith("_shibsession_")
    ][0]
    return {f"{shib_key}": s.cookies.get_dict()[shib_key]}


def beautify_html(txt: str) -> str:
    res = re.sub(r'<[^>]+?>', '\n', txt)
    res = re.sub(r'\s+', '', res)
    res = re.sub(r'(?:\r\n|\r|\n)+', '\n', res)
    return res


def get_message():
    headers = {"User-Agent": UA}

    cookies = get_shib()

    url = urllib.parse.urljoin(MANADA_URL, NOTICE_URL)
    r = requests.get(url, cookies=cookies, headers=headers)
    if 'query' in NOTICE_URL:
        title = re.search(r'<tr class=title>(.*?)</tr>', r.text, re.MULTILINE | re.DOTALL)
        title = re.search(r'>(.*?)</th>', title.group(1), re.MULTILINE | re.DOTALL)
        title = title.group(1).strip()

        text = re.search(r'<td.*?>(.*?)</td>', r.text[r.text.find('課題に関する説明'):], re.MULTILINE | re.DOTALL)
        text = text.group(1)
    elif 'news' in NOTICE_URL:
        title = re.search(r'<div class="msg-title">(.*?)</div>', r.text, re.MULTILINE | re.DOTALL)
        title = re.search(r'>(.*?)</h2>', title.group(1), re.MULTILINE | re.DOTALL)
        title = title.group(1)

        text = re.search(r'<div class="msg-text">(.*?)</div>', r.text, re.MULTILINE | re.DOTALL)
        text = text.group(1)
    elif 'report' in NOTICE_URL:
        title = re.search(r'<tr class=title>(.*?)</tr>', r.text, re.MULTILINE | re.DOTALL)
        title = re.search(r'>(.*?)</th>', title.group(1), re.MULTILINE | re.DOTALL)
        title = title.group(1).strip()

        text = re.search(r'<td.*?>(.*?)</td>', r.text[r.text.find('問題'):], re.MULTILINE | re.DOTALL)
        text = text.group(1)
    else:
        raise Exception(f"Parse Error")
    title = beautify_html(title)
    text = beautify_html(text)
    embed = discord.Embed(title=title, url=url, color=0x33C7FF)
    embed.add_field(name="内容", value=text, inline=True)
    return embed


def send_msg(msg: discord.Embed):
    client = discord.Client(intents=discord.Intents.default())

    @client.event
    async def on_ready():
        await client.get_channel(CHANNEL).send(embed=msg)
        await client.close()

    client.run(TOKEN)


def send_err(msg: str):
    client = discord.Client(intents=discord.Intents.default())

    @client.event
    async def on_ready():
        await client.get_channel(CHANNEL).send(f"```{msg}```")
        await client.close()

    client.run(TOKEN)


if __name__ == "__main__":
    try:
        send_msg(get_message())
    except Exception:
        send_err(traceback.format_exc())
