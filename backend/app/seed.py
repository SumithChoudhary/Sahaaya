"""Fictional, reproducible sample data used by the local demo database."""

AREAS = [
    {"area_id":"AR-01","name":"Zone Alpha","latitude":19.076,"longitude":72.877,"population_affected":12400,"severity":5,"injured_people":184,"trapped_people":62,"emergency_requests":47,"accessibility":2,"distance_to_resource_center":3.2,"priority_score":94,"priority_class":"Critical","status":"Monitoring"},
    {"area_id":"AR-02","name":"Zone Bravo","latitude":19.105,"longitude":72.854,"population_affected":8900,"severity":4,"injured_people":112,"trapped_people":35,"emergency_requests":31,"accessibility":3,"distance_to_resource_center":4.1,"priority_score":82,"priority_class":"High","status":"Monitoring"},
    {"area_id":"AR-03","name":"Zone Charlie","latitude":19.045,"longitude":72.910,"population_affected":6700,"severity":4,"injured_people":86,"trapped_people":21,"emergency_requests":28,"accessibility":2,"distance_to_resource_center":6.5,"priority_score":76,"priority_class":"High","status":"Monitoring"},
    {"area_id":"AR-04","name":"Zone Delta","latitude":19.130,"longitude":72.900,"population_affected":5200,"severity":3,"injured_people":48,"trapped_people":12,"emergency_requests":18,"accessibility":4,"distance_to_resource_center":5.0,"priority_score":61,"priority_class":"Medium","status":"Monitoring"},
    {"area_id":"AR-05","name":"Zone Echo","latitude":19.020,"longitude":72.840,"population_affected":3800,"severity":2,"injured_people":24,"trapped_people":4,"emergency_requests":12,"accessibility":4,"distance_to_resource_center":7.2,"priority_score":48,"priority_class":"Medium","status":"Monitoring"},
    {"area_id":"AR-06","name":"Zone Foxtrot","latitude":19.160,"longitude":72.870,"population_affected":2700,"severity":2,"injured_people":15,"trapped_people":3,"emergency_requests":8,"accessibility":5,"distance_to_resource_center":2.4,"priority_score":32,"priority_class":"Low","status":"Monitoring"},
    {"area_id":"AR-07","name":"Zone Golf","latitude":19.065,"longitude":72.820,"population_affected":6100,"severity":4,"injured_people":73,"trapped_people":18,"emergency_requests":22,"accessibility":3,"distance_to_resource_center":4.7,"priority_score":73,"priority_class":"High","status":"Monitoring"},
    {"area_id":"AR-08","name":"Zone Hotel","latitude":19.110,"longitude":72.930,"population_affected":1900,"severity":1,"injured_people":9,"trapped_people":1,"emergency_requests":5,"accessibility":5,"distance_to_resource_center":8.0,"priority_score":24,"priority_class":"Low","status":"Monitoring"},
    {"area_id":"AR-09","name":"Zone India","latitude":19.000,"longitude":72.890,"population_affected":7400,"severity":5,"injured_people":132,"trapped_people":41,"emergency_requests":36,"accessibility":2,"distance_to_resource_center":5.8,"priority_score":89,"priority_class":"Critical","status":"Monitoring"},
    {"area_id":"AR-10","name":"Zone Juliet","latitude":19.145,"longitude":72.830,"population_affected":4300,"severity":3,"injured_people":39,"trapped_people":8,"emergency_requests":14,"accessibility":3,"distance_to_resource_center":6.1,"priority_score":54,"priority_class":"Medium","status":"Monitoring"},
]

CENTERS = [
    {"name":"North Ridge Resource Center","latitude":19.15,"longitude":72.88},
    {"name":"East Valley Resource Center","latitude":19.12,"longitude":72.94},
    {"name":"Central Field Resource Center","latitude":19.075,"longitude":72.86},
    {"name":"South Gate Resource Center","latitude":19.015,"longitude":72.865},
    {"name":"West Point Resource Center","latitude":19.055,"longitude":72.815},
]

RESOURCES = [
    {"resource_key":"ambulances","name":"Ambulances","total":42,"available":24,"allocated":10,"deployed":8,"unit":"vehicles","center_name":"Central Field Resource Center"},
    {"resource_key":"rescue-teams","name":"Rescue teams","total":26,"available":18,"allocated":5,"deployed":3,"unit":"teams","center_name":"North Ridge Resource Center"},
    {"resource_key":"medical-kits","name":"Medical kits","total":2200,"available":1240,"allocated":480,"deployed":320,"unit":"kits","center_name":"East Valley Resource Center"},
    {"resource_key":"food-kits","name":"Food kits","total":2600,"available":1780,"allocated":300,"deployed":200,"unit":"kits","center_name":"West Point Resource Center"},
    {"resource_key":"water-units","name":"Water units","total":1500,"available":920,"allocated":250,"deployed":180,"unit":"units","center_name":"Central Field Resource Center"},
    {"resource_key":"shelter-capacity","name":"Shelter capacity","total":1200,"available":680,"allocated":220,"deployed":160,"unit":"beds","center_name":"South Gate Resource Center"},
    {"resource_key":"emergency-transport","name":"Emergency transport","total":20,"available":12,"allocated":4,"deployed":2,"unit":"vehicles","center_name":"South Gate Resource Center"},
]

REQUESTS = [
    {"request_id":"RQ-001","area_id":"AR-01","request_type":"Medical","severity":"Critical","people_affected":12,"status":"Pending"},
    {"request_id":"RQ-002","area_id":"AR-01","request_type":"Rescue","severity":"Critical","people_affected":15,"status":"Processing"},
    {"request_id":"RQ-003","area_id":"AR-01","request_type":"Water","severity":"High","people_affected":20,"status":"Assigned"},
    {"request_id":"RQ-004","area_id":"AR-02","request_type":"Medical","severity":"High","people_affected":8,"status":"Pending"},
    {"request_id":"RQ-005","area_id":"AR-02","request_type":"Food","severity":"Medium","people_affected":23,"status":"Processing"},
    {"request_id":"RQ-006","area_id":"AR-03","request_type":"Rescue","severity":"High","people_affected":5,"status":"Pending"},
    {"request_id":"RQ-007","area_id":"AR-03","request_type":"Water","severity":"Medium","people_affected":23,"status":"Completed"},
    {"request_id":"RQ-008","area_id":"AR-04","request_type":"Medical","severity":"Medium","people_affected":3,"status":"Pending"},
    {"request_id":"RQ-009","area_id":"AR-04","request_type":"Shelter","severity":"Medium","people_affected":15,"status":"Processing"},
    {"request_id":"RQ-010","area_id":"AR-05","request_type":"Food","severity":"Medium","people_affected":2,"status":"Pending"},
    {"request_id":"RQ-011","area_id":"AR-05","request_type":"Shelter","severity":"Low","people_affected":10,"status":"Completed"},
    {"request_id":"RQ-012","area_id":"AR-06","request_type":"Water","severity":"Low","people_affected":8,"status":"Completed"},
    {"request_id":"RQ-013","area_id":"AR-07","request_type":"Evacuation","severity":"High","people_affected":1,"status":"Pending"},
    {"request_id":"RQ-014","area_id":"AR-07","request_type":"Medical","severity":"High","people_affected":21,"status":"Assigned"},
    {"request_id":"RQ-015","area_id":"AR-08","request_type":"Shelter","severity":"Low","people_affected":5,"status":"Completed"},
    {"request_id":"RQ-016","area_id":"AR-09","request_type":"Medical","severity":"Critical","people_affected":2,"status":"Pending"},
    {"request_id":"RQ-017","area_id":"AR-09","request_type":"Rescue","severity":"Critical","people_affected":34,"status":"Processing"},
    {"request_id":"RQ-018","area_id":"AR-10","request_type":"Medical","severity":"Medium","people_affected":1,"status":"Pending"},
    {"request_id":"RQ-019","area_id":"AR-10","request_type":"Water","severity":"Low","people_affected":13,"status":"Completed"},
]

ALERTS = [
    {"alert_id":"AL-001","severity":"Critical","title":"Critical area in demo data","message":"Zone Alpha · Sample priority score 94","area_id":"AR-01","is_read":False},
    {"alert_id":"AL-002","severity":"Warning","title":"Sample resource threshold","message":"Medical kit demo availability is below 60%","area_id":None,"is_read":False},
    {"alert_id":"AL-003","severity":"Info","title":"Sample request group added","message":"Pending medical requests from Zone India","area_id":"AR-09","is_read":False},
]
