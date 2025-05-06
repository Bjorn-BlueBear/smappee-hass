# This is a home assistant integration for the EV Line for Smappee

## How to setup?
As of now there is no oauth flow or anything available.
The early stages only supports one pole also.

### Step 1 
Edit you configuration.yaml file and add the following lines
`
- select:
  platform: **carcharger**
  host: "app1pub.smappee.net/dev"
  client_id: Your client id
  client_secret: Your client secret
  username: the username used for auhtentication
  password: the password for your account
  charger_id: The serial number of your ev charger
  charger_position: The position of your charger (0 or 1)

- number:
  platform: **carcharger**
  host: "app1pub.smappee.net/dev"
  client_id: Your client id
  client_secret: Your client secret
  username: the username used for auhtentication
  password: the password for your account
  charger_id: The serial number of your ev charger
  charger_position: The position of your charger (0 or 1)
`
