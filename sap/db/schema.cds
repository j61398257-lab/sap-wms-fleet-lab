using { cuid } from '@sap/cds/common';

namespace sap.ewm;

entity HandlingTasks : cuid {
    warehouse      : String(4);
    taskNo         : String(20);
    orderNo        : String(20);
    product        : String(40);
    qty            : Decimal(13, 3);
    uom            : String(3);
    srcBin         : String(40);
    dstBin         : String(40);
    priority       : String(10);
    // CREATED 已创建，RELEASED 已下达，IN_PROCESS 执行中，
    // CONFIRMED 已确认，CANCELLED 已取消，EXCEPTION 异常
    status         : String(20);
    actualQty      : Decimal(13, 3);
    exceptionCode  : String(20);
    exceptionText  : String(255);
    cancelRequested : Boolean default false;
    externalRef    : String(80);
    fleetOrder     : String(80);
    modifiedAt     : Timestamp @odata.etag;
}
