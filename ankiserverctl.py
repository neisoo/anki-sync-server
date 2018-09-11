#!/usr/bin/env python

import os
import sys
import signal
import subprocess
import binascii
import getpass
import hashlib
import sqlite3

SERVERCONFIG = "production.ini" # 默认的服务配置文件
AUTHDBPATH = "auth.db"          # 记录用户名和密码的数据库
PIDPATH = "/tmp/ankiserver.pid" # 存放已经启动的后台服务进程id
COLLECTIONPATH = "collections/" # 存放所有用户数据的目录

#使用帮助
def usage():
    print "usage: "+sys.argv[0]+" <command> [<args>]"
    print
    print "Commands:"
    print "  start [configfile] - start the server"
    print "  debug [configfile] - start the server in debug mode"
    print "  stop               - stop the server"
    print "  adduser <username> - add a new user"
    print "  deluser <username> - delete a user"
    print "  lsuser             - list users"
    print "  passwd <username>  - change password of a user"

#启动服务
# 执行paster server configpath启动一个python基于的WSGI结构的Web服务器
# 使用时需要以example.ini为模板复制成production.ini做为configpath。
# debug: false表示启动一个后台进程来运行服务。true表示在前台运行
#        在后台执行时会将台台进程的pid记录在PIDPATH文件，关闭
#        服务时会从这个文件中读回进程pid，并kill进程。
# configpath：传递给命令的配置文件路径
def startsrv(configpath, debug):
    if not configpath:
        configpath = SERVERCONFIG

    # We change to the directory containing the config file
    # so that all the paths will be relative to it.
    configdir = os.path.dirname(configpath)
    if configdir != '':
        os.chdir(configdir)
    configpath = os.path.basename(configpath)

    if debug:
        # Start it in the foreground and wait for it to complete.
        subprocess.call( ["paster", "serve", configpath], shell=False)
        return

    devnull = open(os.devnull, "w")
    pid = subprocess.Popen( ["paster", "serve", configpath],
                            stdout=devnull,
                            stderr=devnull).pid

    with open(PIDPATH, "w") as pidfile:
        pidfile.write(str(pid))

#停止服务
# 从PIDPATH文件中读回startsrv创建的后台进程pid，并kill进程。
def stopsrv():
    if os.path.isfile(PIDPATH):
        try:
            with open(PIDPATH) as pidfile:
                pid = int(pidfile.read())

                os.kill(pid, signal.SIGKILL)
                os.remove(PIDPATH)
        except Exception, error:
            print >>sys.stderr, sys.argv[0]+": Failed to stop server: "+error.message
    else:
        print >>sys.stderr, sys.argv[0]+": The server is not running"

#增加一个新的用户
# 向AUTHDBPATH数据库中插入一条用户记录。并创建存放用户数据目录
def adduser(username):
    if username:
        print "Enter password for "+username+": "

        password = getpass.getpass()
        salt = binascii.b2a_hex(os.urandom(8))
        hash = hashlib.sha256(username+password+salt).hexdigest()+salt

        conn = sqlite3.connect(AUTHDBPATH)
        cursor = conn.cursor()

        cursor.execute( "CREATE TABLE IF NOT EXISTS auth "
                        "(user VARCHAR PRIMARY KEY, hash VARCHAR)")

        cursor.execute("INSERT INTO auth VALUES (?, ?)", (username, hash))

        if not os.path.isdir(COLLECTIONPATH+username):
            os.makedirs(COLLECTIONPATH+username)

        conn.commit()
        conn.close()
    else:
        usage()

#删除用户
# 从用户数据库中删除用户记录，用户数据目录中的文件不会删除。
def deluser(username):
    if username and os.path.isfile(AUTHDBPATH):
            conn = sqlite3.connect(AUTHDBPATH)
            cursor = conn.cursor()

            cursor.execute("DELETE FROM auth WHERE user=?", (username,))

            conn.commit()
            conn.close()
    elif not username:
        usage()
    else:
        print >>sys.stderr, sys.argv[0]+": Database file does not exist"

#列出用户
# 列出数据库中的所有用户记录。
def lsuser():
    conn = sqlite3.connect(AUTHDBPATH)
    cursor = conn.cursor()

    cursor.execute("SELECT user FROM auth")

    row = cursor.fetchone()

    while row is not None:
        print row[0]

        row = cursor.fetchone()

    conn.close()

#修改用户密码
def passwd(username):
    if os.path.isfile(AUTHDBPATH):
        print "Enter password for "+username+": "

        password = getpass.getpass()
        salt = binascii.b2a_hex(os.urandom(8))
        hash = hashlib.sha256(username+password+salt).hexdigest()+salt

        conn = sqlite3.connect(AUTHDBPATH)
        cursor = conn.cursor()

        cursor.execute("UPDATE auth SET hash=? WHERE user=?", (hash, username))

        conn.commit()
        conn.close()
    else:
        print >>sys.stderr, sys.argv[0]+": Database file does not exist"

#根据命令行参数执行相应的功能。
def main():
    argc = len(sys.argv)
    exitcode = 0

    if argc < 2:
        usage()
        exitcode = 1
    else:
        if argc < 3:
            sys.argv.append(None)

        if sys.argv[1] == "start":
            startsrv(sys.argv[2], False)
        elif sys.argv[1] == "debug":
            startsrv(sys.argv[2], True)
        elif sys.argv[1] == "stop":
            stopsrv()
        elif sys.argv[1] == "adduser":
            adduser(sys.argv[2])
        elif sys.argv[1] == "deluser":
            deluser(sys.argv[2])
        elif sys.argv[1] == "lsuser":
            lsuser()
        elif sys.argv[1] == "passwd":
            passwd(sys.argv[2])
        else:
            usage()
            exitcode = 1

    sys.exit(exitcode)

#入口
if __name__ == "__main__":
    main()
