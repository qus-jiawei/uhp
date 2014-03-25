
uhpApp.controller('NarCtrl',['$scope','$rootScope','$interval','$http',function($scope,$rootScope,$interval,$http){
	$scope.user={}
	$scope.menus={}
	$scope.submenus={}
	$http({
	        method: 'GET',
	        url: '/adminback/user'
	    }).success(function(response, status, headers, config){
	        $scope.menus = response["menus"];
	        $scope.user= response["user"];
	        //TODO 判断深度连接使用adminmenus或者usermenus
	        $scope.submenus = response["menus"]["submenus"];
	    }).error(function(data, status) {
	        $scope.status = status;
	    });
	$rootScope.isActiveSubmenu=function(submenu){
		if($rootScope.submenu == submenu) return "active";
		else return "";
	}
	//轮询指定的执行任务，获取进度。在任务地方想调用进度条。
	//调用$rootScope.beginProgress即可传入任务id的数组
	$rootScope.beginProgress=function(id,callback){
		$rootScope.runningId = id;
		$("#progressModal").modal();
		$rootScope.progress=0;
		$rootScope.progressMessage="";
		$rootScope.progressCallback=callback;
		$rootScope.close=false;
		$rootScope.updateProgress();
		$rootScope.success=false;
		stop = $interval($rootScope.updateProgress, 1000);
	}
	$rootScope.updateProgress=function(){
		if( $rootScope.close ) return;
//		console.log(angular.toJson($rootScope.runningId))
		$http({
	        method: 'GET',
	        url: '/adminback/query_progress',
	        params:  { "id" : angular.toJson($rootScope.runningId) }
	    }).success(function(response, status, headers, config){
	    	$rootScope.progressMessage = response['progressMsg'];
	    	if( $rootScope.progress != response['progress'] ){
	    		$rootScope.progress = response['progress'];
	    	}
	    }).error(function(data, status) {
	    	$rootScope.alert("发送query_progress请求失败");
	        $rootScope.closeProgress()
	    });
		
		if( $rootScope.progress == 100 ){
			$rootScope.successProgress();
		}
	}
	$rootScope.successProgress=function(){
		if (angular.isDefined(stop)) {
	      $interval.cancel(stop);
	      stop = undefined;
	    }
		$rootScope.success=true;
		if( $rootScope.progressCallback !=null ){
			$rootScope.progressCallback();
		}
	}
	$rootScope.closeProgress=function(){
		if (angular.isDefined(stop)) {
	      $interval.cancel(stop);
	      stop = undefined;
	    }
		$("#progressModal").modal('hide');
		if( $rootScope.progressCallback !=null ){
			$rootScope.progressCallback();
		}
	}
	$rootScope.initAlerts=function(){
		var temp = getCookie("alerts")
		if( temp != null && temp != "" ){
			$rootScope.alerts = angular.fromJson(temp)
		}
		else{
			$rootScope.alerts = []
		}
		if( $rootScope.alerts.length == 0 ){
			$rootScope.alerts.push({"msg": "welcome to uhp !!","type":"info"})
		} 
		setCookie("alerts",angular.toJson($rootScope.alerts),{"expireSeconds":300});
	}
	$rootScope.initAlerts()
	$rootScope.alert=function(msg,type){
		var temp = getCookie("alerts")
		if( temp != null && temp != "" ){
			$rootScope.alerts = angular.fromJson(temp)
		}
		if( type == null || type==""){
			type="danger"
		}
		if( type == "now"){
			alert(msg);
			return;
		}
		var msgHead = get_now_hms();
		if( type == "danger" ){
			msgHead +=" ERROR ";
		}
		else if( type == "info" ){
			msgHead +=" INFO ";
		}
		else if( type == "warn" ){
			msgHead +=" WARN ";
		}
		else if( type == "welcome" ){
			return
		}
		$rootScope.alerts.unshift({"msg": msgHead+msg,"type":type});
		if($rootScope.alerts.length>10){
			$rootScope.alerts.splice(0, 1);
		}
		setCookie("alerts",angular.toJson($rootScope.alerts),{"expireSeconds":300});
	}
	$rootScope.closeAlert = function(index) {
		$rootScope.alerts.splice(index, 1);
		//$cookieStore.put("alerts",$rootScope.alerts);
		setCookie("alerts",angular.toJson($rootScope.alerts),{"expireSeconds":300});
	};
	
	$rootScope.showFirst = function(){
		if($rootScope.first !=null && $rootScope.first == false) return
		$rootScope.alert("初次安装请到设置进行必要的配置,星号的配置请留意","warn")
		$rootScope.first = false;
	}

	//自动刷新,各个ctrl通过registerAutoFlush注册要自动刷新的函数
	//autoFlush会自动根据submenus名字选择自动刷新的函数并调用
	$rootScope.autoFlushMap = {}
	$rootScope.registerAutoFlush = function(submenu,initFun){
		$rootScope.autoFlushMap[submenu] = initFun;
	}
	$rootScope.autoFlush = function(){
		var initFun = $rootScope.autoFlushMap[$rootScope.submenu]
		if( initFun != null){
			initFun()
		}
	}
	$rootScope.beginAutoFlush = function(){
		stop = $interval($rootScope.autoFlush, 5000);
	}
	$rootScope.beginAutoFlush()
}])