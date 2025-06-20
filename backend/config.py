class Config:
    # MySQL数据库连接配置
    # 注意：kwok用户只允许从192.168.200.1主机连接
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://kwok:Onjuju1084@192.168.200.10/campusnet_db?charset=utf8mb4"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_POOL_RECYCLE = 280  # 连接池回收时间，单位为秒
