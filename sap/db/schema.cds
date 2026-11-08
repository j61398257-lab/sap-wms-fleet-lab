namespace sap.ewm;

// 状态码沿用 EWM：'' 未清，'D' 执行中（仅仓库单），'C' 已确认，'A' 已取消
entity WarehouseOrders {
    key EWMWarehouse            : String(4);
    key WarehouseOrder          : String(10);
        WarehouseOrderStatus    : String(1) default '';
        ExecutingResource       : String(18) default '';
        _WarehouseTask          : Association to many WarehouseTasks
                                      on  _WarehouseTask.EWMWarehouse   = EWMWarehouse
                                      and _WarehouseTask.WarehouseOrder = WarehouseOrder;
}

entity WarehouseTasks {
    key EWMWarehouse                 : String(4);
    key WarehouseTask                : String(12);
    key WarehouseTaskItem            : String(4);
        WarehouseOrder               : String(10);
        WarehouseTaskStatus          : String(1) default '';
        WarehouseProcessType         : String(4);
        Product                      : String(40);
        TargetQuantityInAltvUnit     : Decimal(13, 3);
        ActualQuantityInAltvUnit     : Decimal(13, 3) default 0;
        AlternativeUnit              : String(3);
        SourceStorageBin             : String(18);
        DestinationStorageBin        : String(18);
        SourceHandlingUnit           : String(20) default '';
        WhseTaskCrtnUTCDateTime      : Timestamp;
        WarehouseTaskConfUTCDateTime : Timestamp;
        LastChangeUTCDateTime        : Timestamp @odata.etag;
}
