import requests
import json
import os
import sys

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
    # 必须与获取 Cookie 时的登录设备一致；当前账号在 macOS Chrome 登录。
    useragent = os.environ.get("USER_AGENT", "").strip() or (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
    )
    payload = {"token": "glados.cloud"}

    for account_index, cookie in enumerate(cookies, start=1):
        print(f"处理账号 {account_index}/{len(cookies)}")
        checkin = requests.post(
            url,
            headers={
                "cookie": cookie,
                "referer": referer,
                "origin": origin,
                "user-agent": useragent,
                "content-type": "application/json;charset=UTF-8",
            },
            data=json.dumps(payload),
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
