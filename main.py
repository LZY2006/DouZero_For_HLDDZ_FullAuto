# -*- coding: utf-8 -*-
# Created by: Raf
# Modify by: Vincentzyx
# Modify by: LZY

# import GameHelper as gh
# from GameHelper import GameHelper
import os
import sys
import time
import threading
import pyautogui
import win32gui
from PIL import Image
import multiprocessing as mp

from PyQt5 import QtGui, QtWidgets, QtCore
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsPixmapItem, QInputDialog, QMessageBox
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import QTime, QEventLoop, pyqtRemoveInputHook
from MainWindow import Ui_Form

from douzero.env.game import GameEnv
from douzero.evaluation.deep_agent import DeepAgent

import BidModel
import LandlordModel
import FarmerModel

EnvCard2RealCard = {3: '3', 4: '4', 5: '5', 6: '6', 7: '7',
                    8: '8', 9: '9', 10: 'T', 11: 'J', 12: 'Q',
                    13: 'K', 14: 'A', 17: '2', 20: 'X', 30: 'D'}

RealCard2EnvCard = {'3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
                    '8': 8, '9': 9, 'T': 10, 'J': 11, 'Q': 12,
                    'K': 13, 'A': 14, '2': 17, 'X': 20, 'D': 30}

AllEnvCard = [3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6, 6, 6, 7, 7, 7, 7,
              8, 8, 8, 8, 9, 9, 9, 9, 10, 10, 10, 10, 11, 11, 11, 11, 12,
              12, 12, 12, 13, 13, 13, 13, 14, 14, 14, 14, 17, 17, 17, 17, 20, 30]

AllCards = ['rD', 'bX', 'b2', 'r2', 'bA', 'rA', 'bK', 'rK', 'bQ', 'rQ', 'bJ', 'rJ', 'bT', 'rT',
            'b9', 'r9', 'b8', 'r8', 'b7', 'r7', 'b6', 'r6', 'b5', 'r5', 'b4', 'r4', 'b3', 'r3']


class MyPyQT_Form(QtWidgets.QWidget, Ui_Form):
    def __init__(self):
        super(MyPyQT_Form, self).__init__()
        self.setupUi(self)
        self.setWindowFlags(QtCore.Qt.WindowMinimizeButtonHint |  # 使能最小化按钮
                            QtCore.Qt.WindowCloseButtonHint)  # 窗体总在最前端 QtCore.Qt.WindowStaysOnTopHint
        self.setFixedSize(self.width(), self.height())  # 固定窗体大小
        # self.setWindowIcon(QIcon('pics/favicon.ico'))
        window_pale = QtGui.QPalette()
        # window_pale.setBrush(self.backgroundRole(), QtGui.QBrush(QtGui.QPixmap("pics/bg.png")))
        self.setPalette(window_pale)
        self.Players = [self.RPlayer, self.Player, self.LPlayer]
        self.counter = QTime()

        # 参数
        self.RunGame = False
        self.AutoPlay = False
        # 信号量
        self.shouldExit = 0  # 通知上一轮记牌结束
        self.canRecord = threading.Lock()  # 开始记牌
        self.card_play_model_path_dict = {
            'landlord': r"C:\Users\zdwxx\Documents\Tencent Files\1182338055\FileRecv\landlord_weights_34831802500.ckpt",
            'landlord_up': r"C:\Users\zdwxx\Documents\Tencent Files\1182338055\FileRecv\landlord_up_weights_34831802500.ckpt",
            'landlord_down': r"C:\Users\zdwxx\Documents\Tencent Files\1182338055\FileRecv\landlord_down_weights_34831802500.ckpt"
        }

    def init_display(self):
        self.WinRate.setText("胜率")
        self.InitCard.setText("开始")
        self.UserHandCards.setText("手牌")
        self.LPlayedCard.setText("上家出牌区域")
        self.RPlayedCard.setText("下家出牌区域")
        self.PredictedCard.setText("AI出牌区域")
        self.ThreeLandlordCards.setText("地主牌")
        self.SwitchMode.setText("自动" if self.AutoPlay else "单局")
        for player in self.Players:
            player.setStyleSheet('background-color: rgba(255, 0, 0, 0);')

    def switch_mode(self):
        self.AutoPlay = not self.AutoPlay
        self.SwitchMode.setText("自动" if self.AutoPlay else "单局")

    def init_cards(self):
        self.RunGame = True
        # GameHelper.Interrupt = False
        self.init_display()
        # 玩家手牌
        # self.user_hand_cards_real = ""
        self.user_hand_cards_env = []
        # 其他玩家出牌
        self.other_played_cards_real = ""
        self.other_played_cards_env = []
        # 其他玩家手牌（整副牌减去玩家手牌，后续再减掉历史出牌）
        self.other_hand_cards = []
        # 三张底牌
        # self.three_landlord_cards_real = ""
        self.three_landlord_cards_env = []
        # 玩家角色代码：0-地主上家, 1-地主, 2-地主下家
        # self.user_position_code = None
        self.user_position = ""
        # 开局时三个玩家的手牌
        self.card_play_data_list = {}
        # 出牌顺序：0-玩家出牌, 1-玩家下家出牌, 2-玩家上家出牌
        self.play_order = 0

        self.env = None

        # 识别玩家手牌
        # self.user_hand_cards_real = self.find_my_cards()
        try:
            self.user_hand_cards_real
        except NameError:
            self.user_hand_cards_real = self.find_my_cards()

        self.UserHandCards.setText(self.user_hand_cards_real)
        self.user_hand_cards_env = [RealCard2EnvCard[c] for c in list(self.user_hand_cards_real)]
        # 识别三张底牌
        try:
            self.three_landlord_cards_real
        except NameError:
            self.three_landlord_cards_real = self.find_three_landlord_cards()

        self.ThreeLandlordCards.setText("底牌：" + self.three_landlord_cards_real)
        self.three_landlord_cards_env = [RealCard2EnvCard[c] for c in list(self.three_landlord_cards_real)]
        # 识别玩家的角色
        try:
            self.user_position_code
        except NameError:
            self.user_position_code = self.find_landlord()
        if self.user_position_code is None:
            items = ("地主上家", "地主", "地主下家")
            item, okPressed = QInputDialog.getItem(self, "选择角色", "未识别到地主，请手动选择角色:", items, 0, False)
            if okPressed and item:
                self.user_position_code = items.index(item)
            else:
                return
        self.user_position = ['landlord_up', 'landlord', 'landlord_down'][self.user_position_code]
        for player in self.Players:
            player.setStyleSheet('background-color: rgba(255, 0, 0, 0);')
        self.Players[self.user_position_code].setStyleSheet('background-color: rgba(255, 0, 0, 0.1);')

        # 整副牌减去玩家手上的牌，就是其他人的手牌,再分配给另外两个角色（如何分配对AI判断没有影响）
        for i in set(AllEnvCard):
            self.other_hand_cards.extend([i] * (AllEnvCard.count(i) - self.user_hand_cards_env.count(i)))
        self.card_play_data_list.update({
            'three_landlord_cards': self.three_landlord_cards_env,
            ['landlord_up', 'landlord', 'landlord_down'][(self.user_position_code + 0) % 3]:
                self.user_hand_cards_env,
            ['landlord_up', 'landlord', 'landlord_down'][(self.user_position_code + 1) % 3]:
                self.other_hand_cards[0:17] if (self.user_position_code + 1) % 3 != 1 else self.other_hand_cards[17:],
            ['landlord_up', 'landlord', 'landlord_down'][(self.user_position_code + 2) % 3]:
                self.other_hand_cards[0:17] if (self.user_position_code + 1) % 3 == 1 else self.other_hand_cards[17:]
        })
        print("开始对局")
        print("手牌:",self.user_hand_cards_real)
        print("地主牌:",self.three_landlord_cards_real)
        # 生成手牌结束，校验手牌数量
        if len(self.card_play_data_list["three_landlord_cards"]) != 3:
            QMessageBox.critical(self, "底牌识别出错", "底牌必须是3张！", QMessageBox.Yes, QMessageBox.Yes)
            self.init_display()
            return
        if len(self.card_play_data_list["landlord_up"]) != 17 or \
                len(self.card_play_data_list["landlord_down"]) != 17 or \
                len(self.card_play_data_list["landlord"]) != 20:
            QMessageBox.critical(self, "手牌识别出错", "初始手牌数目有误", QMessageBox.Yes, QMessageBox.Yes)
            self.init_display()
            return
        # 得到出牌顺序
        self.play_order = 0 if self.user_position == "landlord" else 1 if self.user_position == "landlord_up" else 2

        # 创建一个代表玩家的AI
        ai_players = [0, 0]
        ai_players[0] = self.user_position
        ai_players[1] = DeepAgent(self.user_position, self.card_play_model_path_dict[self.user_position])

        self.env = GameEnv(ai_players)
        try:
            self.start()
        except:
            self.stop()

    def start(self):
        self.env.card_play_init(self.card_play_data_list)
        print("开始出牌\n")
        while not self.env.game_over:
            # 玩家出牌时就通过智能体获取action，否则通过识别获取其他玩家出牌
            if self.play_order == 0:
                self.PredictedCard.setText("...")
                action_message = self.env.step(self.user_position)
                # 更新界面
                self.UserHandCards.setText("手牌：" + str(''.join(
                    [EnvCard2RealCard[c] for c in self.env.info_sets[self.user_position].player_hand_cards]))[::-1])

                self.PredictedCard.setText(action_message["action"] if action_message["action"] else "不出")
                self.WinRate.setText("胜率：" + action_message["win_rate"])
                print("\n手牌：", str(''.join(
                    [EnvCard2RealCard[c] for c in self.env.info_sets[self.user_position].player_hand_cards])))
                print("出牌：", action_message["action"] if action_message["action"] else "不出", "， 胜率：",
                      action_message["win_rate"])
                if action_message["action"] == "":
                    # helper.ClickOnImage("pass_btn", region=self.PassBtnPos)
                    print("AI: pass")
                else:
                    # helper.SelectCards(action_message["action"]
                    print("AI:", action_message["action"])
                    tryCount = 20
                self.detect_start_btn()
                self.play_order = 1
            elif self.play_order == 1:
                self.RPlayedCard.setText("...")
                if True:
                    # 识别下家出牌
                    self.RPlayedCard.setText("识别中")
                    print("输入下家出牌")
                    self.other_played_cards_real = self.find_other_cards()
                    print("下家出牌", self.other_played_cards_real)
                    # self.sleep(500)
                # 找到"不出"
                else:
                    self.other_played_cards_real = ""
                print("\n下家出牌：", self.other_played_cards_real)
                self.other_played_cards_env = [RealCard2EnvCard[c] for c in list(self.other_played_cards_real)]
                self.env.step(self.user_position, self.other_played_cards_env)
                # 更新界面
                self.RPlayedCard.setText(self.other_played_cards_real if self.other_played_cards_real else "不出")
                self.play_order = 2
            elif self.play_order == 2:
                self.LPlayedCard.setText("...")
                self.detect_start_btn()
                if True:
                    # 识别上家出牌
                    self.LPlayedCard.setText("等待动画")
                    # self.sleep(1200)
                    self.LPlayedCard.setText("识别中")
                    print("输入上家出牌")
                    self.other_played_cards_real = self.find_other_cards()
                # 找到"不出"
                else:
                    self.other_played_cards_real = ""
                print("\n上家出牌：", self.other_played_cards_real)
                self.other_played_cards_env = [RealCard2EnvCard[c] for c in list(self.other_played_cards_real)]
                self.env.step(self.user_position, self.other_played_cards_env)
                self.play_order = 0
                # 更新界面
                self.LPlayedCard.setText(self.other_played_cards_real if self.other_played_cards_real else "不出")
                # self.sleep(500)
            else:
                pass
            # self.sleep(100)

        print("{}胜，本局结束!\n".format("农民" if self.env.winner == "farmer" else "地主"))
        self.detect_start_btn()

    def find_landlord(self):
        while True:
            x = input("谁是地主？[0]上家 [1]自己 [2]下家")
            if x == "0":
                return 0
            elif x == "1":
                return 1
            elif x == "2":
                return 2
            else:
                continue

    def detect_start_btn(self):
        pass


    def find_three_landlord_cards(self):
        three_landlord_cards_real = ""
        while True:
            x = input("输入3张地主牌:")
            if len(x) != 3:
                print("数量不对")
                continue
            c = input("确定吗？[y]/n")
            if c == "y" or c == "Y" or c == "":
                break
            else:
                continue
        three_landlord_cards_real = x
        return three_landlord_cards_real

    def find_my_cards(self):
        user_hand_cards_real = ""
        while True:
            x = input("输入所有手牌:")
            if len(x) != 17 and len(x) != 20:
                print("数量不对")
                continue
            c = input("确定吗？[y]/n")
            if c == "y" or c == "Y" or c == "":
                break
            else:
                continue
        user_hand_cards_real = x
        return user_hand_cards_real

    def find_other_cards(self):
        while True:
            other_played_cards_real = input("输入牌:")
            c = input("确定吗？[y]/n")
            if c == "" or c == "y" or c == "Y":
                break
        return other_played_cards_real

    def cards_filter(self, location, distance):  # 牌检测结果滤波
        if len(location) == 0:
            return 0
        locList = [location[0][0]]
        count = 1
        for e in location:
            flag = 1  # “是新的”标志
            for have in locList:
                if abs(e[0] - have) <= distance:
                    flag = 0
                    break
            if flag:
                count += 1
                locList.append(e[0])
        return count

    def have_white(self, pos):  # 是否有白块
        pass

    def stop(self):
        try:
            self.RunGame = False
            self.env.game_over = True
            self.env.reset()
            self.init_display()
            self.PreWinrate.setText("局前预估胜率：")
            self.BidWinrate.setText("叫牌预估胜率：")
        except AttributeError as e:
            pass
        if self.AutoPlay:
            input("准备开始")

    def beforeStart(self):
        while True:
            self.detect_start_btn()
            cards_str = self.find_my_cards()
            win_rate = BidModel.predict(cards_str)
            print("预计叫地主胜率：", win_rate)
            self.BidWinrate.setText("叫牌预估胜率：" + str(round(win_rate, 2)) + "%")
            
            llcards = self.find_three_landlord_cards()
            print("地主牌:", llcards)
            user_position_code = self.find_landlord()
            if user_position_code == 1:
                cards_str += llcards
                cards_list = sorted(list(cards_str),key=lambda x:RealCard2EnvCard[x])
                cards_str = str().join(cards_list)
                print("当前手牌：", cards_str)
            if len(cards_str) == 20:
                win_rate = LandlordModel.predict(cards_str)
                self.PreWinrate.setText("局前预估胜率：" + str(round(win_rate, 2)) + "%")
                print("预估地主胜率:", win_rate)
            else:
                
                user_position = "up"
                while user_position_code is None:
                    user_position_code = self.find_landlord()
                    # self.sleep(50)
                user_position = ['up', 'landlord', 'down'][user_position_code]
                win_rate = FarmerModel.predict(cards_str, llcards, user_position) - 5
                print("预估农民胜率:", win_rate)
                self.PreWinrate.setText("局前预估胜率：" + str(round(win_rate, 2)) + "%")
            break

        self.user_hand_cards_real = cards_str
        self.three_landlord_cards_real = llcards
        self.user_position_code = user_position_code
        self.init_cards()


if __name__ == '__main__':
    pyqtRemoveInputHook()
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet("""
    QPushButton{
        text-align : center;
        background-color : white;
        font: bold;
        border-color: gray;
        border-width: 2px;
        border-radius: 10px;
        padding: 6px;
        height : 14px;
        border-style: outset;
        font : 14px;
    }
    QPushButton:hover{
        background-color : light gray;
    }
    QPushButton:pressed{
        text-align : center;
        background-color : gray;
        font: bold;
        border-color: gray;
        border-width: 2px;
        border-radius: 10px;
        padding: 6px;
        height : 14px;
        border-style: outset;
        font : 14px;
        padding-left:9px;
        padding-top:9px;
    }
    QComboBox{
        background:transparent;
        border: 1px solid rgba(200, 200, 200, 100);
        font-weight: bold;
    }
    QComboBox:drop-down{
        border: 0px;
    }
    QComboBox QAbstractItemView:item{
        height: 30px;
    }
    QLabel{
        background:transparent;
        font-weight: bold;
    }
    """)
    my_pyqt_form = MyPyQT_Form()
    my_pyqt_form.show()
    sys.exit(app.exec_())
