#-*- encoding: utf-8 -*-

import tornado.web
import config

from datetime import datetime, timedelta
import admin_base_handler
from common import redis_cache, state, error
from helper import str_helper, http_helper
from proxy import soc_right_proxy
from logic import project_logic, product_logic, task_logic

class TaskProjectListHandler(admin_base_handler.AdminRightBaseHandler):
    _rightKey = config.SOCPMConfig['appCode'] + '.AppManager'
    _right = state.operView

    def _format_project_tasks(self, tasks, isEdit):
        ''' 格式化任务列表。需要格式化 preindex, level '''
        if None == tasks or len(tasks) <= 0:
            tasks = []
            if isEdit:
                tasks.append({'startDate': str_helper.get_now_datestr(), 'endDate': str_helper.get_now_datestr(),
                    'date': 1, 'parentID': 0, 'id': 0, 'preindex': 0, 'sort': 1, 'preID': 0, 'users': '', 
                    'degree': 0, 'userName': '', 'name': '', 'level': 1, 'status': 0, 'userRealName': ''})
            return tasks
        indexMap = {}
        #格式化 statusname，level        
        for task in tasks:
            if task['parentID'] == 0:
                task['level'] = 1
            else:
                task['level'] = indexMap.get(task['parentID'], {}).get('level', 0) + 1
            indexMap[task['id']] = {'index': task['sort'], 'level':task['level']}
        #格式化 preindex
        temp = []
        for task in tasks:
            if task['preID'] > 0:
                task['preindex'] = indexMap.get(task['preID'], {}).get('index', 0)
            else:
                task['preindex'] = 0
            temp.append(task)
        return temp


    def get(self):
        ps = self.get_page_config('项目任务列表')
        ps['projects'] = project_logic.ProjectLogic.instance().query_all_by_active()

        if None == ps['projects'] or len(ps['projects']) <= 0:
            ps['projectID'] = 0
            ps['projects'] = []
            ps['tasks'] = []
            ps['msg'] = state.ResultInfo.get(111003, '')
            ps['gotoUrl'] = ps['siteDomain'] + 'Admin/Project/Add'
            self.render('admin/task/project_task_list.html', **ps)
            return

        ps['projectID'] = int(self.get_arg('projectID', '0'))
        if ps['projectID'] <= 0:
            ps['projectID'] = ps['projects'][0]['id']

        tasks = task_logic.TaskLogic.instance().query_by_projectID(projectID = ps['projectID'])
        tasks = self._format_project_tasks(tasks, False)
        ps['tasks'] = tasks
        self.render('admin/task/project_task_list.html', **ps)

class TaskProjectAddOrEditHandler(TaskProjectListHandler):
    _rightKey = config.SOCPMConfig['appCode'] + '.AppManager'
    _right = 0

    def get(self):
        ps = self.get_page_config('编辑任务')
        ps['projects'] = project_logic.ProjectLogic.instance().query_all_by_active()

        projectID = int(self.get_arg('projectID', '0'))
        if None == ps['projects'] or len(ps['projects']) <= 0:
            ps['msg'] = state.ResultInfo.get(112006, '')
            ps['gotoUrl'] = ps['siteDomain'] + 'Admin/Project/Add'            
            self.render('admin/task/project_task_add_or_edit.html', **ps)
            return

        if projectID <= 0:
            projectID = ps['projects'][0]['id']

        ps['projectID'] = projectID        
        ps['users'] = project_logic.ProjectLogic.instance().query_user_by_project_distinct(projectID = projectID)

        tasks = task_logic.TaskLogic.instance().query_by_projectID(projectID = projectID)
        tasks = self._format_project_tasks(tasks, True)

        ps['tasks'] = tasks
        self.render('admin/task/project_task_add_or_edit.html', **ps)



    def _format_post_tasks(self, users):
        tasks = []
        index = int(self.get_arg('taskCount', '1')) + 1        
        userMap = {}
        for user in users:
            userMap[user['userName']] = user['userRealName']        
        for i in range(1, index):
            ind = str(i)
            task = {}
            task['sort'] = i
            task['name'] = self.get_arg('task_'+ind, '')            
            task['level'] = int(self.get_arg('level_'+ind, '1'))
            task['type'] = 1
            task['parentID'] = int(self.get_arg('parentID_'+ind, '0'))
            task['status'] = int(self.get_arg('status_'+ind, '0'))
            task['taskID'] = int(self.get_arg('taskID_'+ind, '0'))
            task['id'] = task['taskID']
            task['date'] = int(self.get_arg('date_'+ind, '1'))
            task['startDate'] = self.get_arg('startDate_'+ind, '')
            task['endDate'] = self.get_arg('endDate_'+ind, '')
            task['preID'] = int(self.get_arg('pre_'+ind, '0'))
            task['preindex'] = task['preID']
            task['degree'] = int(self.get_arg('degree_'+ind, '0'))
            task['userName'] = self.get_arg('user_'+ind, '')
            task['userRealName'] = userMap.get(task['userName'], '')
            task['users'] = self.get_arg('users_'+ind, '')
            tasks.append(task)
        return tasks


    def post(self):
        ps = self.get_page_config('编辑任务')
        ps['projects'] = project_logic.ProjectLogic.instance().query_all_by_active()
        ps['projectID'] = int(self.get_arg('projectID', '0'))
        ps['users'] = project_logic.ProjectLogic.instance().query_user_by_project_distinct(projectID = ps['projectID'])

        if None == ps['projects'] or len(ps['projects']) <= 0:
            ps['msg'] = state.ResultInfo.get(112006, '')
            ps['gotoUrl'] = ps['siteDomain'] + 'Admin/Project/Add'            
            self.render('admin/task/project_task_add_or_edit.html', **ps)
            return
        
        ps['tasks'] = self._format_post_tasks(users = ps['users'])
        ps['user'] = self.get_oper_user()
        try:
            info = task_logic.TaskLogic.instance().save_tasks(projectID = ps['projectID'], 
                tasks = ps['tasks'], user = ps['user'])
            if info:
                self.redirect(ps['siteDomain'] + 'Admin/Task/ProjectList?projectID='+str(ps['projectID']))
                return
            else:
                ps['msg'] = state.ResultInfo.get(101, '')
        except error.RightError as e:
            ps['msg'] = e.msg
        ps = self.format_none_to_empty(ps)
        self.render('admin/task/project_task_add_or_edit.html', **ps)




class TaskListHandler(admin_base_handler.AdminRightBaseHandler):
    _rightKey = config.SOCPMConfig['appCode'] + '.AppManager'
    _right = state.operView

    def _get_user_list(self):
        users = []
        for role in state.ProjectRoles:
            title = role['name']
            us = soc_right_proxy.get_users_by_usergroup(userGroupID = config.SOCPMConfig['RoleUserGroup'][role['id']])
            if None != us and len(us) > 0:
                for u in us:
                    t = True
                    for user in users:
                        if user['userName'] == u['userName']:
                            t = False
                            break
                    if True == t:
                        users.append(u)
        return users


    def get(self):
        ps = self.get_page_config('任务列表')
        ps['users'] = self._get_user_list()

        if None == ps['users'] or len(ps['users']) <= 0:            
            self.render('admin/task/project_task_list.html', **ps)
            return
        ps['user'] = self.get_oper_user()
        ps['type'] = state.TaskTypes
        ps['status'] = state.TaskStatus

        task = self.get_args(['userName', 'startDate', 'endDate'], '')
        if '0' == task['userName']:
            task['userName'] = ''
        elif '' == task['userName']:            
            task['userName'] = ps['user']

        task['status'] = self.get_arg('status', '')
        if '' == task['status']:
            task['status'] = state.TaskRunningStatus
        else:
            task['status'] = int(task['status'])
        task['type'] = int(self.get_arg('type', '0'))
        ps['page'] = int(self.get_arg('page', '1'))

        ps['pagedata'] = task_logic.TaskLogic.instance().query_by_type_userName_status_begin_end(
                        type = task['type'], userName = task['userName'], status = task['status'],
                        startDate = task['startDate'], endDate = task['endDate'], 
                        page = ps['page'], size = ps['size'])
                        
        ps['pager'] = self.build_page_html(page = ps['page'], size = ps['size'], total = ps['pagedata']['total'], pageTotal = ps['pagedata']['pagetotal'])        
        ps['task'] = task
        ps = self.format_none_to_empty(ps)
        self.render('admin/task/list.html', **ps)



class TaskAddOrEditHandler(TaskListHandler):
    _rightKey = config.SOCPMConfig['appCode'] + '.AppManager'
    _right = 0

    def get(self):
        ps = self.get_page_config('创建非项目计划任务') 
        ps['users'] = self._get_user_list()
        if None == ps['users'] or len(ps['users']) <= 0:            
            self.render('admin/task/project_task_list.html', **ps)
            return

        ps['user'] = self.get_oper_user()
        ps['types'] = [s for s in state.TaskTypes if s['id'] != state.TaskProjectPlanType] 

        if ps['isedit']:
            ps['title'] = self.get_page_title('编辑非项目计划任务')
            id = int(self.get_arg('id', '0'))
            task = task_logic.TaskLogic.instance().query_one(id = id)
            if None == task or task['type'] == state.TaskProjectPlanType:
                ps['msg'] = state.ResultInfo.get(112007, '')
                ps['gotoUrl'] = ps['siteDomain'] + 'Admin/Task/List'
                task = {'id':'','name':'','type':'','projectID':'','userName':'','userRealName':'','date':'','startDate':'','endDate':'','users':'','preID':'','parentID':'','sort':'','status':'', 'statusname': '','degree':'','remark':'','creater':'','createTime':'','lastUpdater':'','lastUpdateTime':''}
        else:
            task = {'id':'','name':'','type':'','projectID':'','userName':'','userRealName':'','date':'','startDate':'','endDate':'','users':'','preID':'','parentID':'','sort':'','status':'','degree':'','remark':'','creater':'','createTime':'','lastUpdater':'','lastUpdateTime':''}
            task['userName'] = self.get_arg('userName', '')
            task['startDate'] = datetime.now()
            task['endDate'] = datetime.now()
            task['degree'] = '0'

        ps['task'] = task
        ps = self.format_none_to_empty(ps)
        self.render('admin/task/add_or_edit.html', **ps)


    def post(self):
        ps = self.get_page_config('创建非项目计划任务') 
        if ps['isedit']:
            ps['title'] = self.get_page_title('编辑非项目计划任务')

        ps['users'] = self._get_user_list()
        if None == ps['users'] or len(ps['users']) <= 0:            
            self.render('admin/task/project_task_list.html', **ps)
            return
        ps['user'] = self.get_oper_user()

        task = self.get_args(['name','userName','userRealName','startDate','endDate','users','remark'], '')
        task['degree'] = int(self.get_arg('degree', '0'))
        task['type'] = int(self.get_arg('type', '0'))
        task['id'] = int(self.get_arg('id', '0'))

        ps['task'] = task

        msg = self.check_str_empty_input(task, ['name', 'userName', 'userRealName', 'startDate', 'endDate'])
        if str_helper.is_null_or_empty(msg) == False:
            ps['msg'] = msg
            self.render('admin/task/add_or_edit.html', **ps)
            return

        if ps['isedit']:
            try:
                info = task_logic.TaskLogic.instance().update(id = task['id'], name = task['name'], 
                        userName = task['userName'], userRealName = task['userRealName'], date = 1, 
                        startDate = task['startDate'], endDate = task['endDate'], users = task['users'], 
                        degree = task['degree'], remark = task['remark'], user = ps['user'])
                if info:
                    self.redirect(ps['siteDomain'] + 'Admin/Task/List')
                    return 
                else:
                    ps['msg'] = state.ResultInfo.get(101, '')
            except error.ProjectError as e:
                ps['msg'] = e.msg
        else:
            # self.check_oper_right(right = state.operAdd)
            status = task_logic.TaskLogic.instance().get_task_status(degree = task['degree'])
            try:
                info = task_logic.TaskLogic.instance().add(name = task['name'], type = task['type'], projectID = 0,
                        userName = task['userName'], userRealName = task['userRealName'], date = 1, startDate = task['startDate'],
                        endDate = task['endDate'], users = task['users'], preID = 0, parentID = 0, sort = 0, status = status, 
                        degree = task['degree'], remark = task['remark'], user = ps['user'])
                if info > 0:
                    self.redirect(ps['siteDomain'] + 'Admin/Task/List')
                    return
                else:
                    ps['msg'] = state.ResultInfo.get(101, '')
            except error.ProjectError as e:
                ps['msg'] = e.msg
        ps = self.format_none_to_empty(ps)
        self.render('admin/task/add_or_edit.html', **ps)



class TaskStatusAddOrEditHandler(TaskProjectListHandler):
    _rightKey = config.SOCPMConfig['appCode'] + '.AppManager'
    _right = 0

    def get(self):
        ps = self.get_page_config('编辑任务状态')        
        
        id = int(self.get_arg('id', '0'))

        if id <= 0:
            ps['msg'] = state.ResultInfo.get(112007, '')
            ps['gotoUrl'] = ps['siteDomain'] + 'Admin/Task/ProjectList'            
            self.render('admin/task/edit_status.html', **ps)
            return

        task = task_logic.TaskLogic.instance().query_one(id = id)        
        ps['task'] = task
        ps = self.format_none_to_empty(ps)
        self.render('admin/task/edit_status.html', **ps)
        

    def post(self):
        ps = self.get_page_config('编辑任务')        
        id = int(self.get_arg('id', '0'))
        if id <= 0:
            ps['msg'] = state.ResultInfo.get(112007, '')
            ps['gotoUrl'] = ps['siteDomain'] + 'Admin/Task/ProjectList'            
            self.render('admin/task/edit_status.html', **ps)
            return

        task = task_logic.TaskLogic.instance().query_one(id = id)
        task['users'] = self.get_arg('users', '')
        task['remark'] = self.get_arg('remark', '')
        task['degree'] = int(self.get_arg('degree', '0'))

        ps['user'] = self.get_oper_user()
        if 0 <= task['degree'] and 100 >= task['degree']:
            try:
                info = task_logic.TaskLogic.instance().update_degree_remark(
                            id = task['id'], degree = task['degree'], users = task['users'], remark = task['remark'], user = ps['user'])
                if info:
                    self.redirect(ps['siteDomain'] + 'Admin/Task/ProjectList?projectID='+str(task['projectID']))
                    return
                else:
                    ps['msg'] = state.ResultInfo.get(101, '')
            except error.ProjectError as e:
                ps['msg'] = e.msg
        else:
            ps['msg'] = state.ResultInfo.get(112008, '')
        ps['task'] = task
        ps = self.format_none_to_empty(ps)
        self.render('admin/task/edit_status.html', **ps)


class TaskDetailHandler(admin_base_handler.AdminRightBaseHandler):
    _rightKey = config.SOCPMConfig['appCode'] + '.AppManager'
    _right = state.operView

    def get(self):
        ps = self.get_page_config('任务详情')
        id = int(self.get_arg('id', '0'))
        task = task_logic.TaskLogic.instance().query_one(id = id)
        if None == task:
            ps['msg'] = state.ResultInfo.get(112007, '')
            ps['gotoUrl'] = ps['siteDomain'] + 'Admin/Task/ProjectList'
            product = {'id':'','name':'','teamPath':'','productUserName':'','productUserRealName':'',
                            'devUserName':'','devUserRealName':'', 'startDate':'', 'endDate':''
                            ,'remark':'','status':1,'creater':'', 
                            'createTime':'','lastUpdater':'','lastUpdateTime':'', 'projects':[]}
        project['projects'] = product_logic.ProductLogic.instance().query_all_by_project(project['id'])
        ps['project'] = project
        self.render('admin/project/detail.html', **ps)



