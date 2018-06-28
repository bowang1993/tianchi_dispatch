'''
Created on Jun 25, 2018

@author: Heng.Zhang
'''

from MachineRes import *
from AppRes import *
from global_param import *
 
class MachineRunningInfo(object):
    def __init__(self, each_machine):
        self.running_machine_res = MachineRes(each_machine)  # 剩余的资源
        self.machine_res = MachineRes(each_machine) # 机器的资源
        self.running_inst_list = []
        self.running_app_dict = {}
        return
    
    # ratio 为 1 或 -1，  dispatch app 时 为 -1， 释放app时 为 1
    def update_machine_res(self, inst_id, app_res, ratio):
        self.running_machine_res.update_machine_res(app_res, ratio)

        if (ratio == DISPATCH_RATIO):
            self.running_inst_list.append(inst_id)
            if (app_res.app_id not in self.running_app_dict):
                self.running_app_dict[app_res.app_id] = 0

            self.running_app_dict[app_res.app_id] += 1
        else:
            self.running_inst_list.remove(inst_id)
            
            self.running_app_dict[app_res.app_id] -= 1
            if (self.running_app_dict[app_res.app_id] == 0):
                self.running_app_dict.pop(app_res.app_id)

        return True
    
    def print_remaining_res(self, inst_app_dict, app_res_dict):
        for each_inst in self.running_inst_list:
            print(getCurrentTime(), '%s, %s ' % (each_inst, app_res_dict[inst_app_dict[each_inst][0]].to_string()))
            
        print(getCurrentTime(), self.running_machine_res.to_string())
    
    # cpu 使用率低于0.5 的归为一类
    def get_cpu_percentage(self):
        return max(self.running_machine_res.cpu_percentage - 0.5, 0)
    
    def get_cpu_useage(self):
        return self.running_machine_res.cpu_useage
    
    # 得到剩余可用资源
    def get_res_sum(self):
        return self.running_machine_res.get_res_sum()
    
    # 查看机器总的资源是否能容纳 app
    def meet_inst_res_require(self, app_res):
        return self.machine_res.meet_inst_res_require(app_res)
    
    # 是否可以将 app_res 分发到当前机器
    def can_dispatch(self, app_res, app_constraint_dict):
        
        # 需要迁入的 app 在当前机器上运行的实例数
        immmigrate_app_running_inst = 0
        if (app_res.app_id in self.running_app_dict):
            immmigrate_app_running_inst = self.running_app_dict[app_res.app_id]

        # 在当前机器上运行的 app 与需要迁入的 app 是否有约束，有约束的话看 immmigrate_app_running_inst 是否满足约束条件
        # 不满足约束的情况下 1. 不能部署在当前机器上，  2. 迁移走某些 app 使得可以部署
        # 当前先实现 1
        for app_id, inst_cnt in self.running_app_dict.items():
            if (app_id in app_constraint_dict and app_res.app_id in app_constraint_dict[app_id] and
                immmigrate_app_running_inst >= app_constraint_dict[app_id][app_res.app_id]):
                return False

        # 满足约束条件，看剩余资源是否满足
        return self.running_machine_res.meet_inst_res_require(app_res)

    def dispatch_app(self, inst_id, app_res, app_constraint_dict):
        if (self.can_dispatch(app_res, app_constraint_dict)):
            self.update_machine_res(inst_id, app_res, DISPATCH_RATIO)
            return True

        return False
    
    def release_app(self, inst_id, app_res):
        if (inst_id in self.running_inst_list):
            self.update_machine_res(inst_id, app_res, RELEASE_RATIO)
            return True
        
        return False

    # 为了将  immgrate_inst_id 迁入， 需要将 running_inst_list 中的一个或多个 inst 迁出，
    # 迁出的规则为： 满足迁入app cpu 的最小值，迁出的 app 越多越好，越多表示迁出的 app cpu 越分散，迁移到其他机器上也就越容易
    def cost_of_immigrate_app(self, immgrate_inst_id, inst_app_dict, app_res_dict, app_constraint_dict):
       
        candidate_apps_list_of_machine = []
        # 候选 迁出  inst list 的长度从 1 到 len(self.runing_app_list)
        for inst_list_size in range(1, len(self.running_inst_list) + 1):
            end_idx_of_running_set = len(self.running_inst_list) - inst_list_size + 1 
            for i in range(end_idx_of_running_set): 
                cur_inst_list = [self.running_inst_list[i]]
                self.find_migratable_app(cur_inst_list, inst_list_size - 1, i + 1, \
                                         candidate_apps_list_of_machine, immgrate_inst_id, \
                                         inst_app_dict, app_res_dict, app_constraint_dict)

        # 在所有符合条件的可迁出 app list 中， 找到所有资源之和最小的一个作为该 machine 的迁出 app list
        # 在所有符合条件的可迁出 app list 中， 找到所有资源方差的均值最小的一个作为该 machine 的迁出 app list
        if (len(candidate_apps_list_of_machine) > 0):
            min_sum = 1e9
            min_idx = 0
            for i, each_candidate_list in enumerate(candidate_apps_list_of_machine):
                sum_of_list = AppRes.get_var_mean_of_apps(each_candidate_list, inst_app_dict, app_res_dict)
                if (sum_of_list < min_sum):
                    min_sum = sum_of_list
                    min_idx = i

            return candidate_apps_list_of_machine[min_idx]
        else:
            return []
        
    # 在 running_inst_list 的 [start_idx, end_idx) 范围内， 找到一个 app_list_size 长度的 app_list, 
    # 使得 app_list 的 cpu 满足迁入的  app cpu， 保存起来作为迁出的 app list 候选
    def find_migratable_app(self, cur_inst_list, left_inst_list_size, start_idx,  
                            candidate_apps_list, immgrate_inst_id, inst_app_dict, app_res_dict, app_constraint_dict):
        if (left_inst_list_size == 0):
            # 将要迁出的资源之和
            cpu_slice, mem_slice, disk_usg, p_usg, m_usg, pm_usg = AppRes.sum_app_res(cur_inst_list, inst_app_dict, app_res_dict)

            # 候选的迁出 app list 资源加上剩余的资源 满足迁入的  app cpu， 保存起来作为迁出的 app list 候选
            immigrating_app_res = app_res_dict[inst_app_dict[immgrate_inst_id][0]]
            if (np.all(cpu_slice + self.running_machine_res.cpu_slice >= immigrating_app_res.cpu_slice) and 
                np.all(mem_slice + self.running_machine_res.mem >= immigrating_app_res.mem_slice) and 
                disk_usg + self.running_machine_res.disk >= immigrating_app_res.disk and 
                p_usg + self.running_machine_res.p >= immigrating_app_res.p and 
                m_usg + self.running_machine_res.m >= immigrating_app_res.m and
                pm_usg + self.running_machine_res.pm >= immigrating_app_res.pm):
                candidate_apps_list.append(cur_inst_list)
            return 
        
        for i in range(start_idx, len(self.running_inst_list)):
            self.find_migratable_app(cur_inst_list + [self.running_inst_list[i]], left_inst_list_size - 1, i + 1, 
                                     candidate_apps_list, immgrate_inst_id, inst_app_dict, app_res_dict, app_constraint_dict)
        return