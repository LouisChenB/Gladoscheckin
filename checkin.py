import requests
import json
import os
import sys

# 已验证的服务端设备名称；只有明确返回设备不匹配时才采用此映射。
DEVICE_USER_AGENTS = {
    "macOS": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
    ),
    "Windows": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
    ),
    "Android": (
        "Mozilla/5.0 (Linux; Android 16; Pixel 10) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Mobile Safari/537.36"
    ),
}


def checkin_with_device(url, headers, payload):
    """按服务端返回的登录设备重试一次，并返回本账号最终使用的 User-Agent。"""
    headers = dict(headers)
    response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
    useragent = headers["user-agent"]
    if response.status_code != 200:
        return response, useragent

    result = response.json()
    if not isinstance(result, dict) or result.get("reason") != "device-mismatch":
        return response, useragent

    login_device = result.get("loginDevice")
    matched_agent = DEVICE_USER_AGENTS.get(login_device) if isinstance(login_device, str) else None
    if not matched_agent:
        print(f"无法自动匹配登录设备 {login_device!r}，请配置 USER_AGENT 或重新登录。")
        return response, useragent
    if matched_agent == useragent:
        print(f"已使用 {login_device} 设备配置，服务端仍拒绝，请重新登录更新 Cookie。")
        return response, useragent

    print(
        f"设备不匹配: 登录设备={login_device}, "
        f"请求设备={result.get('currentDevice', '未知')}；自动切换并重试一次。"
    )
    headers["user-agent"] = matched_agent
    response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
    return response, matched_agent


# -------------------------------------------------------------------------------------------
# github workflows
# -------------------------------------------------------------------------------------------
if __name__ == "__main__":
    # pushplus秘钥 申请地址 http://www.pushplus.plus
    sckey = os.environ.get("PUSHPLUS", "")

    # 推送内容
    title = "Glados"
    success, fail = 0, 0  # 成功账号数量 失败账号数量
    sendContent = ""

    # glados账号cookie 直接使用数组 如果使用环境变量需要字符串分割一下
    cookies = [value.strip() for value in os.environ.get("COOKIES", "").split("&") if value.strip()]
    if not cookies:
        print("未获取到COOKIE变量")
        sys.exit(1)

    url = "https://glados.cloud/api/user/checkin"
    url2 = "https://glados.cloud/api/user/status"
    url_points = "https://glados.cloud/api/user/points"
    url_exchange = "https://glados.cloud/api/user/exchange"

    # 积分兑换配置（默认 500 积分换 100 天）
    # 可选值: "plan100" (100积分→10天), "plan200" (200积分→30天), "plan500" (500积分→100天)
    exchange_plan = os.environ.get("EXCHANGE_PLAN", "plan500")
    exchange_thresholds = {"plan100": 100, "plan200": 200, "plan500": 500}

    referer = "https://glados.cloud/console/checkin"
    origin = "https://glados.cloud"
    # USER_AGENT 只作为各账号的初始值；设备不匹配时按账号独立调整。
    initial_useragent = os.environ.get("USER_AGENT", "").strip() or DEVICE_USER_AGENTS["macOS"]
    payload = {"token": "glados.cloud"}

    for account_index, cookie in enumerate(cookies, start=1):
        print(f"处理账号 {account_index}/{len(cookies)}")
        useragent = initial_useragent
        checkin, useragent = checkin_with_device(
            url,
            headers={
                "cookie": cookie,
                "referer": referer,
                "origin": origin,
                "user-agent": useragent,
                "content-type": "application/json;charset=UTF-8",
            },
            payload=payload,
        )
        state = requests.get(
            url2,
            headers={
                "cookie": cookie,
                "referer": referer,
                "origin": origin,
                "user-agent": useragent,
            },
        )
        # 获取积分信息
        points_resp = requests.get(
            url_points,
            headers={
                "cookie": cookie,
                "referer": referer,
                "origin": origin,
                "user-agent": useragent,
            },
        )
        # --------------------------------------------------------------------------------------------------------#
        if checkin.status_code == 200:
            # 解析返回的json数据
            checkin_result = checkin.json()
            status = checkin_result.get("message") or ""
            checkin_code = checkin_result.get("code")
            reason = checkin_result.get("reason")
            print(f"签到响应: code={checkin_code}, reason={reason}, message={status}")
            if reason == "device-mismatch":
                print(
                    f"登录设备={checkin_result.get('loginDevice', '未知')}, "
                    f"请求设备={checkin_result.get('currentDevice', '未知')}；"
                    "请使用登录浏览器的 User-Agent，必要时重新登录。"
                )

            # 获取账号当前状态
            result = state.json()

            if result.get("code") != 0 or not isinstance(result.get("data"), dict):
                print(f"⚠️ 获取账号状态失败: {result.get('message', '未知错误')}，Cookie 可能已过期，请重新获取")
                fail += 1
                email = f"账号 {account_index}"
                message_status = f"账号状态查询失败: {result.get('message', '未知错误')}"
                message_days = "无法获取"
                message_points = "无法获取"
                message_exchange = ""

                exchange_line = ""
                sendContent += f"{'-'*30}\n\
            账号: {email}\n\
            签到情况: {message_status}\n\
            剩余天数: {message_days}\n\
            当前积分: {message_points}\n"

                if cookie == cookies[-1]:
                    sendContent += "-" * 30
                continue

            # 获取剩余时间
            leftdays = int(float(result["data"]["leftDays"]))
            # 获取账号email
            email = result["data"]["email"]

            status_lower = (status or "").lower()
            if reason == "device-mismatch" or checkin_code == 4:
                fail += 1
                message_status = (
                    f"签到被拒绝: {status} "
                    f"(登录设备={checkin_result.get('loginDevice', '未知')}, "
                    f"请求设备={checkin_result.get('currentDevice', '未知')})"
                )
            elif checkin_code in (None, 1) and (
                "repeat" in status_lower or "already" in status_lower
                or "today's observation logged" in status_lower
            ):
                message_status = "今日已签到"
            elif checkin_code == 0 or (checkin_code is None and (
                "checkin!" in status_lower or "checkin success" in status_lower
            )):
                success += 1
                message_status = "签到成功"
            else:
                fail += 1
                message_status = f"签到失败 (code={checkin_code}, API返回: {status})"

            if leftdays is not None:
                message_days = f"{leftdays} 天"
            else:
                message_days = "无法获取剩余天数信息"

            # 获取积分信息
            points = 0
            message_points = "无法获取积分信息"
            message_exchange = ""
            if points_resp.status_code == 200:
                points_result = points_resp.json()
                # 积分在顶层，且为字符串格式，需要转换
                points = int(float(points_result.get("points", "0")))
                message_points = f"{points} 分"

                # 自动兑换天数
                threshold = exchange_thresholds.get(exchange_plan, 500)
                if points >= threshold:
                    exchange_resp = requests.post(
                        url_exchange,
                        headers={
                            "cookie": cookie,
                            "referer": referer,
                            "origin": origin,
                            "user-agent": useragent,
                            "content-type": "application/json;charset=UTF-8",
                        },
                        data=json.dumps({"planType": exchange_plan}),
                    )
                    if exchange_resp.status_code == 200:
                        exchange_result = exchange_resp.json()
                        if exchange_result.get("code") == 0:
                            message_exchange = f"✅ 自动兑换成功 ({exchange_plan})"
                            print(f"兑换成功: {exchange_result}")
                        else:
                            message_exchange = f"❌ 兑换失败: {exchange_result.get('message', '未知错误')}"
                            print(f"兑换失败: {exchange_result}")
                    else:
                        message_exchange = (
                            f"❌ 兑换请求失败 (HTTP {exchange_resp.status_code})"
                        )
        else:
            fail += 1
            email = f"账号 {account_index}"
            message_status = f"签到请求失败 (HTTP {checkin.status_code})"
            message_days = "获取信息失败"
            message_points = "获取信息失败"
            message_exchange = ""

        # 推送内容
        exchange_line = (
            f"            兑换情况: {message_exchange}\n" if message_exchange else ""
        )
        sendContent += f"{'-'*30}\n\
            账号: {email}\n\
            签到情况: {message_status}\n\
            剩余天数: {message_days}\n\
            当前积分: {message_points}\n{exchange_line}"

        if cookie == cookies[-1]:
            sendContent += "-" * 30

    # --------------------------------------------------------------------------------------------------------#
    print("sendContent:" + "\n", sendContent)
    if sckey != "":
        title += f": 成功{success},失败{fail}"
        plusurl = f"http://www.pushplus.plus/send?token={sckey}&title={title}&content={sendContent}"
        r = requests.get(plusurl)
        print(r.status_code)

    # 处理完全部账号并推送后，让 Actions 正确反映业务失败。
    sys.exit(1 if fail else 0)
