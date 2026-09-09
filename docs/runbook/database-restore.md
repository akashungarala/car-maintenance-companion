# Runbook: restoring the database

CloudNativePG takes base backups and streams WAL to OCI Object Storage. That
gives point-in-time recovery, but only if the restore path works — and a backup
that has never been restored is not a backup, it is an untested assumption
about a file.

## Prove it still works (do this quarterly)

```
./scripts/restore-drill.sh
```

Restores the most recent backup into a scratch namespace, verifies a marker
row, and tears the namespace down on exit. It touches nothing in `cmc`. Run it
after any change to the backup configuration, the CNPG version, or the object
storage credentials.

## Is there anything to restore?

Check before you need it, not during an incident:

```
kubectl get backups -n cmc
kubectl get cluster -n cmc cmc-db -o jsonpath='{.status.firstRecoverabilityPoint}'
```

In Grafana, **CMC · Database** shows backup age directly. The _Backup is stale_
alert fires at 26 hours — a daily backup with two hours of slack.

`cnpg_collector_last_failed_backup_timestamp` moving while
`cnpg_collector_last_available_backup_timestamp` stays put means backups are
running and failing, which looks identical to "quiet" on a dashboard that only
shows the last success.

## Restoring for real

A restore creates a **new cluster** from the backup; it never writes into the
running one. That is deliberate — recovering in place turns a data problem into
an outage with no way back.

1. Stop writes. Scale the worker to zero so jobs stop enqueuing, and consider
   scaling the API down if the corruption is being actively written:

   ```
   kubectl scale deploy -n cmc worker --replicas=0
   ```

2. Create a recovery cluster from the backup, targeting a point in time before
   the damage. `infra/k8s/apps/database/cluster.yaml` is the template; a
   recovery cluster adds `spec.bootstrap.recovery` with `recoveryTarget`.

3. Verify the restored data **before** switching anything:

   ```
   kubectl exec -n cmc cmc-db-restore-1 -- psql -U postgres -d cmc -c '<a query that proves the damage is absent>'
   ```

4. Switch the application over by pointing `CMC_DATABASE_URL` at the restored
   cluster, then scale the worker back up.

5. Keep the damaged cluster until you are certain. It is the only remaining
   copy of anything the backup missed.

## What this does not cover

Recovery is limited by backup age plus WAL. The retention policy is 14 days
(`cluster.yaml`), so a problem discovered on day 15 is not recoverable —
which is an argument for noticing problems, not for longer retention.
