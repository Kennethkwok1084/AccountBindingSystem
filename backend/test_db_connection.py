"""
测试MySQL数据库连接脚本
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import pymysql

# 注册PyMySQL作为MySQLdb的替代品
pymysql.install_as_MySQLdb()

# 创建测试应用
app = Flask(__name__)
app.config.from_object("config.Config")
db = SQLAlchemy(app)

def test_connection():
    """测试数据库连接并显示表信息"""
    try:
        # 尝试执行简单查询
        result = db.session.execute("SHOW TABLES").fetchall()
        print("数据库连接成功!")
        if result:
            print("数据库中的表:")
            for table in result:
                print(f"- {table[0]}")
        else:
            print("数据库中没有表")
        
        # 尝试检查数据库版本
        version = db.session.execute("SELECT VERSION()").scalar()
        print(f"MySQL版本: {version}")
        
        return True
    except Exception as e:
        print(f"数据库连接错误: {e}")
        return False

if __name__ == "__main__":
    test_connection()
