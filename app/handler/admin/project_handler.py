#-*- encoding: utf-8 -*-

import tornado.web
import config

from datetime import datetime, timedelta
import admin_base_handler
from common import redis_cache, state, error
from helper import str_helper, http_helper
from proxy import soc_right_proxy
from logic import project_logic, product_logic

class ProjectListHandler(admin_base_handler.AdminRightBaseHandler):
    _rightKey = config.SOCPMConfig['appCode'] + '.AppManager'
    _right = state.operView

    def get(self):
        ps = self.get_page_config('项目列表')
        project = self.get_args(['productUserRealName', 'devUserRealName', 'name'], '')
        project['status'] = int(self.get_arg('status', '0'))
        project['productID'] = int(self.get_arg('productID', '0'))
        ps['projectStatus'] = state.ProjectStatus
        ps['page'] = int(self.get_arg('page', '1'))
        ps['products'] = product_logic.ProductLogic.instance().query_all_by_active()
        ps['pagedata'] = project_logic.ProjectLogic.instance().query_page(name = project['name'], 
                        productUserRealName = project['productUserRealName'], 
                        devUserRealName = project['devUserRealName'], status= project['status'], 
                        page = ps['page'], size = ps['size'])
        ps['project'] = project
        ps['pager'] = self.build_page_html(page = ps['page'], size = ps['size'], total = ps['pagedata']['total'], pageTotal = ps['pagedata']['pagetotal'])        
        self.render('admin/project/list.html', **ps)

class ProjectAddOrEditHandler(admin_base_handler.AdminRightBaseHandler):
    _rightKey = config.SOCPMConfig['appCode'] + '.AppManager'
    _right = 0

    def _init_template_info(self, ps):
        roleUsers = {}
        for role in state.ProjectRoles:
            roleUsers[role['id']] = soc_right_proxy.get_users_by_usergroup(userGroupID = config.SOCPMConfig['RoleUserGroup'][role['id']])            
            
        ps['roleUsers'] = roleUsers
        ps['projectRoles'] = state.ProjectRoles
        ps['projectStatus'] = state.ProjectStatus
        ps['products'] = product_logic.ProductLogic.instance().query_all_by_active()        
        return ps

    def get(self):
        ps = self.get_page_config('创建项目')
        ps = self._init_template_info(ps)
        if ps['isedit']:
            # self.check_oper_right(right = state.operEdit)
            ps['title'] = self.get_page_title('编辑项目')
            id = int(self.get_arg('id', '0'))
            project = project_logic.ProjectLogic.instance().query_one(id)            
            if None == project:
                ps['msg'] = state.ResultInfo.get(111001, '')
                ps['gotoUrl'] = ps['siteDomain'] + 'Admin/Project/List'
                project = {'id':'','name':'','teamPath':'','productUserName':'','productUserRealName':'',
                            'devUserName':'','devUserRealName':'', 'startDate':'', 'endDate':'','remark':'','status':1, 'projects':[], 'users':[]}
            else:
                project['products'] = product_logic.ProductLogic.instance().query_all_by_project(projectID = project['id'])
                project['users'] = project_logic.ProjectLogic.instance().query_user_by_project(projectID = project['id'])
                for user in project['users']:
                    t = user['type']
                    b = False
                    for role in ps['projectRoles']:
                        if role['id'] == t:
                            if role['isOne'] == True:
                                b = True
                            break
                    if b == True:
                        project['userName_'+str(t)] = user['userName']
        else:
            # self.check_oper_right(right = state.operAdd)
            project = self.get_args(['name', 'teamPath', 'productUserName', 'productUserRealName', 
                'devUserName', 'devUserRealName','startDate', 'endDate', 'remark'], '')
            project['status'] = int(self.get_arg('status', '0'))
            project['id'] = int(self.get_arg('id', '0'))
            project['startDate'] = datetime.now()
            project['endDate'] = datetime.now()
            project['products'] = []
            project['users'] = []
        ps['project'] = project
        self.render('admin/project/add_or_edit.html', **ps)


    def post(self):
        ps = self.get_page_config('创建项目')
        if ps['isedit']:
            ps['title'] = self.get_page_title('编辑项目')

        project = self.get_args(['name', 'teamPath', 'productUserName', 'productUserRealName', 
                        'devUserName', 'devUserRealName','startDate', 'endDate', 'remark'], '')
        project['status'] = int(self.get_arg('status', '0'))
        project['id'] = int(self.get_arg('id', '0'))        
        project['productIDs'] = str_helper.format_str_to_list_filter_empty(self.get_arg('productIDs',''), ',')
        project['products'] = product_logic.ProductLogic.instance().query_by_ids(project['productIDs'])

        ps = self._init_template_info(ps)

        '''  获取绑定的用户  BEGIN '''
        users = []
        oneUserNames = {}        
        for role in ps['projectRoles']:
            rid = role['id']
            if role['isOne']:
                #单人
                un = self.get_arg('role_select_'+str(rid), '')
                urn = self.get_arg('user_real_name_'+str(rid), '')
                if un != '':                    
                    project['userName_'+str(rid)] = un
                    users.append({'type':rid, 'userName':un, 'userRealName': urn})
                if rid == state.productManagerRoleID:
                    project['productUserName'] = un
                    project['productUserRealName'] = urn
                elif rid == state.devManagerRoleID:
                    project['devUserName'] = un
                    project['devUserRealName'] = urn
            else:
                #多人
                uns = str_helper.format_str_to_list_filter_empty(self.get_arg('userNames_'+str(rid),''), ',')
                for un in uns:
                    for unn in ps['roleUsers'][rid]:
                        if un != unn['userName']:
                            continue
                        users.append({'type':rid, 'userName':un, 'userRealName': unn['userRealName']})
        '''  获取绑定的用户  END '''
        project['users'] = users

        ps['project'] = project

        if len(project['productIDs']) <= 0:
            ps['msg'] = '请选择产品'
            self.render('admin/project/add_or_edit.html', **ps)
            return

        if len(project['users']) <= 0:
            ps['msg'] = '请选择人员'
            self.render('admin/project/add_or_edit.html', **ps)
            return
        
        msg = self.check_str_empty_input(project, ['name', 'productUserName', 'productUserRealName', 
                            'devUserName', 'devUserRealName','startDate', 'endDate'])
        if str_helper.is_null_or_empty(msg) == False:
            ps['msg'] = msg
            self.render('admin/project/add_or_edit.html', **ps)
            return

        project['user'] = self.get_oper_user()
        if ps['isedit']:
            # self.check_oper_right(right = state.operEdit)
            try:
                info = project_logic.ProjectLogic.instance().update(id = project['id'], name = project['name'], 
                        teamPath = project['teamPath'], productUserName = project['productUserName'], 
                        productUserRealName = project['productUserRealName'], devUserName = project['devUserName'], 
                        devUserRealName = project['devUserRealName'], startDate = project['startDate'], 
                        endDate = project['endDate'], status = project['status'], 
                        remark = project['remark'], user = project['user'], productIDs = project['productIDs'], users = project['users'])
                if info:
                    self.redirect(ps['siteDomain'] + 'Admin/Project/List')
                    return
                else:
                    ps['msg'] = state.ResultInfo.get(101, '')
            except error.ProjectError as e:
                ps['msg'] = e.msg
        else:
            # self.check_oper_right(right = state.operAdd)
            try:
                info = project_logic.ProjectLogic.instance().add(name = project['name'], 
                        teamPath = project['teamPath'], productUserName = project['productUserName'], 
                        productUserRealName = project['productUserRealName'], devUserName = project['devUserName'], 
                        devUserRealName = project['devUserRealName'], startDate = project['startDate'], 
                        endDate = project['endDate'], status = project['status'], 
                        remark = project['remark'], user = project['user'], productIDs = project['productIDs'], users = project['users'])
                if info > 0:
                    self.redirect(ps['siteDomain'] + 'Admin/Project/List')
                    return
                else:
                    ps['msg'] = state.ResultInfo.get(101, '')
            except error.ProjectError as e:
                ps['msg'] = e.msg
        ps = self.format_none_to_empty(ps)
        self.render('admin/project/add_or_edit.html', **ps)



class ProjectDelHandler(admin_base_handler.AdminRightBaseHandler):
    _rightKey = config.SOCPMConfig['appCode'] + '.AppManager'
    _right = state.operDel

    def post(self):
        id = self.get_arg('id', '')
        user = self.get_oper_user()
        type = project_logic.ProjectLogic.instance().delete(id = id, user = user)
        if type:
            self.out_ok()
        else:
            self.out_fail(code = 101)

class ProjectDetailHandler(admin_base_handler.AdminRightBaseHandler):
    _rightKey = config.SOCPMConfig['appCode'] + '.AppManager'
    _right = state.operView

    def get(self):
        ps = self.get_page_config('项目详情')
        id = int(self.get_arg('id', '0'))
        project = project_logic.ProjectLogic.instance().query_one(id)    
        if None == project:
            ps['msg'] = state.ResultInfo.get(111001, '')
            ps['gotoUrl'] = ps['siteDomain'] + 'Admin/Project/List'
            product = {'id':'','name':'','teamPath':'','productUserName':'','productUserRealName':'',
                            'devUserName':'','devUserRealName':'', 'startDate':'', 'endDate':''
                            ,'remark':'','status':1,'creater':'', 
                            'createTime':'','lastUpdater':'','lastUpdateTime':'', 'projects':[]}
        project['projects'] = product_logic.ProductLogic.instance().query_all_by_project(project['id'])
        ps['project'] = project
        self.render('admin/project/detail.html', **ps)


