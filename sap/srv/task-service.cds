using { sap.ewm as ewm } from '../db/schema';

service TaskService {
    entity Tasks as projection on ewm.HandlingTasks actions {
        action release();
        action handover(externalRef : String, fleetOrder : String);
        action confirm(actualQty : Decimal);
        action reportException(code : String, text : String);
        action requestCancel();
        action acceptCancel();
    };
}
