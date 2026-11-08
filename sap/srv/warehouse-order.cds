using { sap.ewm as ewm } from '../db/schema';

@path: '/sap/opu/odata4/sap/api_warehouse_order_task_2/srvd_a2x/sap/warehouseorder/0001'
service com.sap.gateway.srvd_a2x.api_warehouse_order_task_2.v0001 {
    entity WarehouseOrder as projection on ewm.WarehouseOrders;

    entity WarehouseTask as projection on ewm.WarehouseTasks actions {
        action ConfirmWarehouseTaskExact(DirectWhseTaskConfIsAllowed : Boolean) returns WarehouseTask;
        action CancelWarehouseTask() returns WarehouseTask;
    };
}
