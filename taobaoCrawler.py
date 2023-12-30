import pymysql
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pyquery import PyQuery as pq
import time
import random

KEYWORD = '衣服'
MYSQL_TABLE = 'goods'

# MySQL 数据库连接配置
db_config = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '123456',
    'database': 'datavisible',
    'charset': 'utf8mb4',
}

# 创建 MySQL 连接对象
conn = pymysql.connect(**db_config)
cursor = conn.cursor()

options = webdriver.ChromeOptions()
# 关闭自动测试状态显示 // 会导致浏览器报：请停用开发者模式
options.add_experimental_option("excludeSwitches", ['enable-automation'])

# 把chrome设为selenium驱动的浏览器代理；
driver = webdriver.Chrome(options=options)
# 窗口最大化
driver.maximize_window()

# wait是Selenium中的一个等待类，用于在特定条件满足之前等待一定的时间(这里是15秒)。
# 如果一直到等待时间都没满足则会捕获TimeoutException异常
wait = WebDriverWait(driver, 15)

# 打开页面后会强制停止10秒，请在此时手动扫码登陆
def search_goods(start_page, total_pages):
    print('正在搜索: ')
    try:
        driver.get('https://www.taobao.com')
        # 强制停止10秒，请在此时手动扫码登陆
        time.sleep(10)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument",
                           {"source": """Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"""})
        # 找到搜索输入框
        input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#q")))
        # 找到“搜索”按钮
        submit = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'#J_TSearchForm > div.search-button > button')))
        input.send_keys(KEYWORD)
        submit.click()
        # 搜索商品后会再强制停止10秒，如有滑块请手动操作
        time.sleep(10)

        # 如果不是从第一页开始爬取，就滑动到底部输入页面然后跳转
        if start_page != 1 :
            # 滑动到页面底端
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            # 滑动到底部后停留1-3s
            random_sleep(1, 3)

            # 找到输入页面的表单
            pageInput = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="root"]/div/div[3]/div[1]/div[1]/div[2]/div[4]/div/div/span[3]/input')))
            pageInput.send_keys(start_page)
            # 找到页面跳转的确定按钮，并且点击
            admit = wait.until(EC.element_to_be_clickable((By.XPATH,'//*[@id="root"]/div/div[3]/div[1]/div[1]/div[2]/div[4]/div/div/button[3]')))
            admit.click()

        get_goods()

        for i in range(start_page + 1, start_page + total_pages):
            page_turning(i)
    except TimeoutException:
        print("search_goods: error")
        return search_goods()
    

# 进行翻页处理
def page_turning(page_number):
    print('正在翻页: ', page_number)
    try:
        # 找到下一页的按钮
        submit = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="sortBarWrap"]/div[1]/div[2]/div[2]/div[8]/div/button[2]')))
        submit.click()
        # 判断页数是否相等
        wait.until(EC.text_to_be_present_in_element((By.XPATH, '//*[@id="sortBarWrap"]/div[1]/div[2]/div[2]/div[8]/div/span/em'), str(page_number)))
        get_goods()
    except TimeoutException:
        page_turning(page_number)
    

# 强制等待的方法，在timeS到timeE的时间之间随机等待
def random_sleep(timeS, timeE):
    # 生成一个S到E之间的随机等待时间
    random_sleep_time = random.uniform(timeS, timeE)
    time.sleep(random_sleep_time)


#获取每一页的商品信息；
def get_goods():
    # 获取商品前固定等待2-4秒
    random_sleep(2, 4)

    html = driver.page_source
    doc = pq(html)
    # 提取所有商品的共同父元素的类选择器
    items = doc('div.PageContent--contentWrap--mep7AEm > div.LeftLay--leftWrap--xBQipVc > div.LeftLay--leftContent--AMmPNfB > div.Content--content--sgSCZ12 > div > div').items()
    
    for item in items:
        # 定位商品标题
        title = item.find('.Title--title--jCOPvpf span').text()
        # 定位价格
        price_int = item.find('.Price--priceInt--ZlsSi_M').text()
        price_float = item.find('.Price--priceFloat--h2RR0RK').text()
        if price_int and price_float:
            price = float(f"{price_int}{price_float}")
        else:
            price = 0.0
        # 定位交易量
        deal = item.find('.Price--realSales--FhTZc7U').text()
        # 定位所在地信息
        location = item.find('.Price--procity--_7Vt3mX').text()
        # 定位店名
        shop = item.find('.ShopInfo--TextAndPic--yH0AZfx a').text()
        # 定位包邮的位置
        postText = item.find('.SalesPoint--subIconWrapper--s6vanNY span').text()
        result = 1 if "包邮" in postText else 0

        # 构建商品信息字典
        product = {
            'title': title,
            'price': price,
            'deal': deal,
            'location': location,
            'shop': shop,
            'isPostFree': result
        }
        save_to_mysql(product)


# 在 save_to_mysql 函数中保存数据到 MySQL
def save_to_mysql(result):
    try:
        sql = "INSERT INTO {} (price, deal, title, shop, location, postFree) VALUES (%s, %s, %s, %s, %s, %s)".format(MYSQL_TABLE)
        print("sql语句为:  "  + sql)
        cursor.execute(sql, (result['price'], result['deal'], result['title'], result['shop'], result['location'], result['isPostFree']))
        conn.commit()
        print('存储到MySQL成功: ', result)
    except Exception as e:
        print('存储到MYsql出错: ', result, e)


# 在 main 函数开始时连接数据库
def main():
    try:
        pageStart = int(input("输入您想开始爬取的页面数: "))
        pageAll = int(input("输入您想爬取的总页面数: "))
        search_goods(pageStart, pageAll)
    except Exception as e:
        print('main函数报错: ', e)
    finally:
        cursor.close()
        conn.close()

#启动爬虫
if __name__ == '__main__':
    main()