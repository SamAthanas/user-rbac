# 🏠 Home Assistant RBAC Middleware

Finally, a flexible Role-Based Access Control (RBAC) middleware component for Home Assistant that intercepts service calls and enforces access control based on YAML configuration.

## ⚠️ Notice:
This application is under active development and is not stable yet!

## ✨ Features

- **Service Call Interception**: Automatically intercepts all Home Assistant service calls
- **YAML-Based Configuration**: Ability to define access control rules in a YAML file
- **Modernized Frontend for Configuration**: Alternatively use the admin Frontend to configure the access control rules.
- **Domain and Entity Level Control**: Restrict access at both domain and entity levels
- **Action/Service call Control**: Restrict actions on specific domains or entities, or restrict all actions tied to an entity 
- **Dynamic Configuration**: Reload configuration without restarting Home Assistant
- **Notifications+Events**: Persistant notifications and events are sent when system denies action call
- **Service Management**: Built-in services to manage and inspect configuration
- **Deploy Scripts for Development**: vs-code scripts included to auto ssh into server to copy files based on .env variables, and auto restarts HA after deployment for streamlined dev workflow

## 🚀 Installation
- Copy the files to your server first
- Search for the 'RBAC' (Role Based Access Control) Integration and install it
- Ensure you are logged in as an admin user, and then access this page <YOUR_HA_DOMAIN>/local/community/rbac/config.html
- Configure Roles and Role Assignments
- Changes to the config take effect immediantly without any restart needed
- Test with users to ensure denied action calls are blocked

## 💡 Creative Ideas
- Restrict non household users to sensitive domains like 'light', 'camera', or home assistant shutdown services
- Create a guest role that utilizes the current user context in a template to determine if they should have access to your homes entities based on if they are within proximity of your house ('Guest' role is used when they are not at 'home', 'User' role is used if they are at home)

## 📝 Notes
- Admin users or users assigned an admin role will be able to access the RBAC configuration page 
- Its possible to assign templates to each role. Templates will be evaluated each time a user that has that role executes a service call. The template will determine if the users role should be used, or if it should fallback to a different role with an entierly different set of permissions. This makes it possible to create more complex auth systems based on current states from your HA instance.
- Default domain/enttiy blocklists are supported. Any non-admin user will always have these restrictions enforced.
- Currently only a deny list is supported.

## 🤝 Contributing

Contributions are welcome and much appreciated!
There are vscode scripts included to easily deploy changes made to the backend or frontend, and auto retart HA when complete.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.
