# Extended API - Orders Endpoint Reference

## Fetch Orders

```
GET https://ejolie.ro/api/?comenzi&apikey=API_KEY
```

### Parameters

| Param        | Description                | Example      |
| ------------ | -------------------------- | ------------ |
| `data_start` | Start date (DD-MM-YYYY)    | `01-01-2026` |
| `data_end`   | End date (DD-MM-YYYY)      | `31-01-2026` |
| `idstatus`   | Filter by status ID        | `14`         |
| `limit`      | Max records (default 2000) | `2000`       |
| `id_comanda` | Specific order ID          | `12345`      |
| `client`     | Client ID                  | `1234`       |

### Status IDs

| ID  | Name                  | Use             |
| --- | --------------------- | --------------- |
| 1   | Comanda NOUA          | New orders      |
| 2   | Comanda in PROCESARE  | Being processed |
| 4   | Comanda in ASTEPTARE  | On hold         |
| 9   | Comanda RETURNATA     | Returned        |
| 10  | Comanda ANULATA       | Cancelled       |
| 14  | Comanda INCASATA      | Paid/collected  |
| 37  | Comanda SCHIMB        | Exchange        |
| 38  | Comanda REFUZATA      | Refused         |
| 40  | Storno partial Manual | Partial storno  |
| 41  | Merchant REV          | Merchant review |
| 43  | Trendya               | Trendya source  |
| 44  | Smartex               | Smartex source  |

### Response Fields (per order)

| Field                   | Description          |
| ----------------------- | -------------------- |
| `id_comanda`            | Order ID             |
| `data`                  | Date (DD.MM.YYYY)    |
| `status`                | Status name          |
| `status_id`             | Status ID            |
| `total_comanda`         | Order total (RON)    |
| `pret_livrare`          | Shipping cost (RON)  |
| `metoda_plata`          | Payment method name  |
| `metoda_livrare`        | Delivery method name |
| `produse`               | Array of products    |
| `produse.*.nume`        | Product name         |
| `produse.*.pret_unitar` | Unit price           |
| `produse.*.cantitate`   | Quantity             |
| `produse.*.cod`         | Product code         |

## Fetch Statuses

```
GET https://ejolie.ro/api/?status&apikey=API_KEY
```

## Fetch Products

```
GET https://ejolie.ro/api/?produse&apikey=API_KEY&categorie=X&limit=50
```

## Error Handling

All errors return: `{"eroare": 1, "mesaj": "Error description"}`

Common errors:

- Module not active → activate in Manager → Servicii → Integrări
- IP restricted → add IP in Manager → Extended API → Restricții IP
- No permission → enable section in Manager → Extended API → Permisii
