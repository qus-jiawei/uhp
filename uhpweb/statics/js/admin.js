//use base.js
var uhpApp = angular.module('uhpApp', ['ngRoute', 'ngAnimate', 'ngSanitize']);
//,'ui.bootstrap'
//'$cookiesProvider',
//,'localytics.directives'
uhpApp.config(['$routeProvider', "$interpolateProvider",'$rootScopeProvider', function($routeProvider, $interpolateProvider,$rootScopeProvider) {
	$interpolateProvider.startSymbol('[[');
    $interpolateProvider.endSymbol(']]');
    $routeProvider
    	.when('/admin-service',
        {
            controller: 'ServiceCtrl',
            templateUrl: '/statics/partials/admin/service.html'
        })
        .when('/admin-host',
        {
            controller: 'HostsCtrl',
            templateUrl: '/statics/partials/admin/host.html'
        })
        .when('/admin-task',
        {
            controller: 'TaskCtrl',
            templateUrl: '/statics/partials/admin/task.html'
        })
        .when('/admin-setting',
        {
            controller: 'SettingCtrl',
            templateUrl: '/statics/partials/admin/setting.html'
        })
        .when('/admin-template',
        {
            controller: 'SettingCtrl',
            templateUrl: '/statics/partials/admin/template.html'
        })
        .when('/admin-manual',
        {
            controller: 'ManualCtrl',
            templateUrl: '/statics/partials/admin/manual.html'
        })
        .when('/monitor', {
            redirectTo: '/monitor/overview'
        })
        .when('/monitor/overview', {
            controller: 'MoniOverviewCtrl',
            templateUrl: '/statics/partials/monitor/monitor.html'
        })
        .when('/monitor/host', {
            controller: 'MoniHostCtrl',
            templateUrl: '/statics/partials/monitor/monitor.html'
        })
        .when('/monitor/service', {
            controller: 'MoniServiceCtrl',
            templateUrl: '/statics/partials/monitor/monitor.html'
        })
        .when('/monitor/job', {
            controller: 'MoniJobCtrl',
            templateUrl: '/statics/partials/monitor/monitor.html'
        })
        .when('/monitor/conf', {
            controller: 'MoniConfCtrl',
            templateUrl: '/statics/partials/monitor/monitor.html'
        })
        .otherwise({ redirectTo: '/admin-service' });

}]);






