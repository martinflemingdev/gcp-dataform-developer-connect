# Dataform + Developer Connect setup guide

This is the high-level setup model proven by the POC for connecting BigQuery Dataform repositories to GitHub through Developer Connect.

The Crossplane manifests that prove the model live in:

```text
/home/martinfleming/src/github.com/martinflemingdev/crossplane-gcp/Crossplane_GCP-Upbound/04_resources/family/developerconnect
```

The detailed running notes live in:

```text
/home/martinfleming/src/github.com/martinflemingdev/gcp-dataform-developer-connect/setup/02_github_connection_notes.md
```

## Proven result

A Dataform repository in one GCP project can use a Developer Connect GitRepositoryLink from another GCP project when the Dataform repository is created through the API/Crossplane with the full GitRepositoryLink resource name.

The console picker did not expose the central connection/link cleanly, but the API accepted it.

POC platform project:

```text
axial-life-395119
```

POC consuming project:

```text
cdmc-data
```

POC central GitRepositoryLink:

```text
projects/axial-life-395119/locations/australia-southeast1/connections/syd-data-res-crossplane/gitRepositoryLinks/martinflemingdev-gcp-dataform-developer-connect-xp
```

POC cross-project Dataform repository:

```text
projects/cdmc-data/locations/australia-southeast1/repositories/dataform-devconnect-cross-project
```

## Resource model

Developer Connect connections are project- and region-scoped resources. They are not folder-level resources.

The scalable enterprise model from the POC is:

1. Platform project owns the Developer Connect connection.
2. Platform project owns one or more GitRepositoryLinks under that connection.
3. A consuming project creates its own Dataform repository.
4. That Dataform repository references the platform GitRepositoryLink by full resource name.
5. The consuming project's Dataform service agent gets IAM on the platform project/link.
6. The app team still manages Dataform and BigQuery permissions in its own project.

This means a central platform project can vend regional GitRepositoryLink resource names to app teams. The app team's Dataform repository does not need to own the Developer Connect connection.

## API prerequisites

For the consuming project, the explicit API prerequisites for this POC are:

- BigQuery: `bigquery.googleapis.com`
- Dataform: `dataform.googleapis.com`
- Developer Connect: `developerconnect.googleapis.com`

References: [Dataform prerequisites](https://docs.cloud.google.com/dataform/docs/create-repository), [Developer Connect integration prerequisites](https://docs.cloud.google.com/dataform/docs/connect-repository).

The platform project also needs the Developer Connect and Secret Manager APIs for the connection and GitHub App secrets.

## GitHub App model

For data-residency-compliant Developer Connect setup, Google Cloud console creates or uses a dedicated GitHub App owned by the GitHub user or organization running the setup. In this POC the app is owned by `@martinflemingdev`; for enterprise use, the app should normally be owned by the company GitHub organization or enterprise platform owner.

The GitHub App must be installed on each repository that Developer Connect needs to access. That repository installation step is separate from creating the Dataform repository.

Developer Connect exposes two different GitHub connection configurations:

- `githubConfig` uses one of Google's predefined/shared GitHub Apps, such as `DEVELOPER_CONNECT`, plus an OAuth credential. It does not accept a customer-owned GitHub App ID, private key, or webhook secret. Google routes events for this model through its global GitHub App path, so Google documents it as not data-residency compliant.
- `githubEnterpriseConfig` accepts a specific customer-owned GitHub App. For a complete, non-interactive connection to a precreated app, supply `hostUri`, `appId`, `appInstallationId`, `privateKeySecretVersion`, and `webhookSecretSecretVersion`. Despite the field name, this is also the configuration used by this POC's data-residency-compliant connection to ordinary `https://github.com`; the repository can be a normal private GitHub.com repository and does not need to be hosted on GitHub Enterprise Server.

Although the API schema marks some of these fields optional, they are required for this precreated-app workflow to reach a usable state without another interactive setup step. The POC created `syd-data-res-xp-no-app-id` without `appInstallationId`, but it remained at `PENDING_INSTALL_APP`, left `appInstallationId` empty, and returned an `actionUri`; the console confirmed that installation still had to be completed. Resource creation and `Ready=True` in Crossplane therefore do not prove that GitHub installation setup is complete. Check `status.atProvider.installationState` for `stage: COMPLETE`.

References: [Developer Connect connection API](https://docs.cloud.google.com/developer-connect/docs/api/reference/rest/v1/projects.locations.connections), [Developer Connect data residency](https://docs.cloud.google.com/developer-connect/docs/data-residency).

Important GitHub App fields:

- App ID: identifier used by Developer Connect; not a secret.
- Client ID: OAuth identifier; not a secret by itself.
- Client secret: OAuth secret; different from the private key.
- Private key: server-to-server GitHub App credential; sensitive and stored through Secret Manager for Developer Connect.
- Webhook URL and webhook secret: used for GitHub event delivery to Developer Connect; the webhook secret is separate from both the OAuth client secret and private key.
- Private key SHA/fingerprint: not the private key and not enough to reconstruct it, but still redact it from public/customer-facing docs unless it is needed.

## IAM required for a consuming project

There are three separate IAM paths. Do not collapse them.

### 1. Dataform service agent can use the platform Git link

Grant the consuming project's Dataform service agent these roles on the platform project where the Developer Connect connection/link lives:

```text
roles/developerconnect.tokenAccessor
roles/developerconnect.gitProxyUser
```

Principal format:

```text
service-<CONSUMING_PROJECT_NUMBER>@gcp-sa-dataform.iam.gserviceaccount.com
```

POC example:

```text
service-370318638050@gcp-sa-dataform.iam.gserviceaccount.com
```

Grant location:

```text
axial-life-395119
```

That means the grant is made on the platform project, not on `cdmc-data`, even though `cdmc-data` owns the Dataform repository.

### 2. IaC/platform identity can create the Dataform repository

The identity creating the Dataform repository needs permission in the consuming project.

In this POC, Crossplane used:

```text
serviceAccount:crossplane@axial-life-395119.iam.gserviceaccount.com
roles/dataform.admin
```

on:

```text
cdmc-data
```

Without this, the API failed with `dataform.repositories.create` denied.

### 3. Dataform execution identity can run BigQuery work

Developer Connect IAM only authorizes Git access. It does not grant BigQuery execution access.

The Dataform execution identity still needs normal BigQuery permissions, such as:

```text
roles/bigquery.jobUser
```

plus dataset/table access as appropriate.

## Creating the Dataform repository

The Dataform repository must reference the full Developer Connect GitRepositoryLink:

```text
projects/axial-life-395119/locations/australia-southeast1/connections/syd-data-res-crossplane/gitRepositoryLinks/martinflemingdev-gcp-dataform-developer-connect-xp
```

The Crossplane Dataform repository uses:

```yaml
gitRemoteSettings:
  defaultBranch: main
  gitRepositoryLink: projects/axial-life-395119/locations/australia-southeast1/connections/syd-data-res-crossplane/gitRepositoryLinks/martinflemingdev-gcp-dataform-developer-connect-xp
  url: https://github.com/martinflemingdev/gcp-dataform-developer-connect.git
```

Once the Dataform repository is connected to Git, the app team uses Dataform normally: create workspaces, pull from Git, commit/push changes, compile, and run workflows. BigQuery execution permissions remain a separate setup step.

## Proxy and network allowlisting

Proxy disabled means Dataform reaches the Git host directly with Developer Connect credentials. For GitHub Enterprise with IP allowlists, this maps to Dataform regional egress IPs.

Proxy enabled means Dataform reaches the Developer Connect proxy, and the proxy reaches the Git host. The Git host sees the Developer Connect proxy/private-connectivity path, not normal Dataform egress. Do not assume the Dataform egress IP table applies.

The Crossplane-created connection in this POC did not include `gitProxyConfig`, so treat it as proxy disabled unless a separate gcloud/API step enables proxy. The Google Cloud console-created connection had proxy enabled by default.

The console-created link's proxy hostname was tested with DNS on 2026-09-25:

```text
australia-southeast1-git.developerconnect.dev
  CNAME: googlecode.l.googleusercontent.com
  IPv4:  192.178.155.82
  IPv6:  2607:f8b0:4004:c23::52
```

Only the hostname is resolved; the project/connection/repository path in the proxy URL is irrelevant to DNS. These addresses are a point-in-time DNS result behind Google infrastructure, not documented static Developer Connect proxy egress addresses. Do not build a firewall allowlist from `192.178.155.82` or the IPv6 result alone: DNS answers can vary by resolver, client location, routing, and time. Use Google-published ranges or an explicitly supported private-connectivity design for production allowlisting.

## What an app team needs from platform

For each onboarding, platform should provide:

- Region.
- Full GitRepositoryLink resource name.
- Confirmation that the GitHub App is installed on the target GitHub repository.
- Confirmation that the consuming project's Dataform service agent has `roles/developerconnect.tokenAccessor` and `roles/developerconnect.gitProxyUser` on the platform project/link.
- Any network/proxy decision for GitHub Enterprise allowlisting.

The app team still needs its own Dataform repository resource and BigQuery execution IAM.
