# WDG Micro Skeleton

**<span style="color:#B1CD46">WDG Micro Skeleton</span>** is a lightweight and modular boilerplate designed for building Python-based microservices using Django. This template incorporates essential features and best practices, such as environment-specific configurations, Docker integration, automatic skeleton generation, and app removal. It aims to streamline development, promote scalability, and simplify deployment while providing flexibility for adding and removing apps with ease.

## <span style="color:#0077FF">Features</span>

- **Environment-Specific Configurations**: Easily manage different settings for development, production, and other environments.
- **Docker Integration**: Pre-configured Docker support with Dockerfile and docker-compose.yml for seamless containerization and deployment.
- **Automatic Skeleton Generation**: Quickly set up a new microservice or app with the built-in script, creating a project skeleton that includes all essential files and directories.
- **Modular Application Setup**: Scaffold new Django apps within the microservice, ensuring a clean and consistent structure for new features or services.
- **App Removal**: Easily remove apps from the project, including their associated files, configurations, and app structure.

## 📂 Project Boilerplate

```sh
•
├── 📁 wdg_micro_skeleton              # Custom application module
│   ├── 📁 apps                        # Application-specific code
│   │   ├── 📄 __init__.py             # Initialization file for the app
│   │   ├── 📄 core_service.py         # Script cloning a project skeleton
│   │   ├── 📁 core                    # Core components of the app
│   │   │   ├── 📁 exceptions          # Custom exceptions
│   │   │   ├── 📁 management          # Management commands
│   │   │   ├── 📁 middleware          # Custom middleware
│   │   │   ├── 📁 migrations          # Database migrations
│   │   │   ├── 📁 mixins              # Mixin classes for reusability
│   │   │   ├── 📁 models              # Data models for the app
│   │   │   ├── 📁 selectors           # Query logic and data retrieval
│   │   │   ├── 📁 serializers         # Data serializers for API responses
│   │   │   ├── 📁 services            # Core business logic and services
│   │   │   ├── 📁 tests               # Unit tests for the app
│   │   │   ├── 📁 utils               # Utility functions and helpers
│   │   │   ├── 📁 views               # View functions or classes for handling requests
│   │   │   ├── 📄 __init__.py         # Initialization file for the core app
│   │   │   ├── 📄 apps.py             # App-specific settings and configurations
│   │   │   ├── 📄 constants.py        # Constants used across the app
│   │   │   └── 📄 urls.py             # URL routing for the core app
│   ├── 📁 configs                     # Configuration files for the project
│   │   ├── 📁 databases               # Database configuration
│   │   ├── 📁 settings                  # Django-specific configurations
│   │   ├── 📁 exceptions              # General exception configurations
│   │   ├── 📁 extensions              # Project-specific extensions or features
│   │   ├── 📄 __init__.py             # Initialization file for configs
│   │   ├── 📄 asgi.py                 # ASGI configuration
│   │   ├── 📄 celery.py               # Celery configuration for background tasks
│   │   ├── 📄 env.py                  # Environment variable configuration
│   │   ├── 📄 pagination.py           # Pagination settings
│   │   ├── 📄 settings.py             # Main project settings
│   │   ├── 📄 urls.py                 # Main URL routing for the project
│   │   └── 📄 wsgi.py                 # WSGI configuration
│   ├── 📁 requirements                # Project dependencies
│   │   └── 📄 base.txt                # Base dependencies file
│   ├── 📁 storages                    # Storage-related configurations
│   │   ├── 📁 logs                    # Log storage configurations
│   │   └── 📁 security                # Security configurations
│   ├── 📄 __init__.py                 # Initialization file for the module
│   ├── 📄 .env                        # Environment variables file
│   ├── 📄 .env.example                # Example environment variables file
│   ├── 📄 .gitignore                  # Git ignore rules
│   ├── 📄 MANIFEST.in                 # Manifest file for packaging
│   ├── 📄 manage.py                   # Command-line utility for managing the Django project
│   ├── 📄 README.md                   # Project documentation file
│   ├── 📄 requirements.txt            # List of project dependencies
│   ├── 📄 setup.py                    # Setup file for the project
•

```

## <span style="color:#0077FF">Getting Started</span>

Take a few minutes to set up your project with a well-structured foundation using WDG Micro Skeleton. This boilerplate provides a ready-made structure to help you quickly build and scale Python-based microservices with Django, ensuring best practices from the start.

### <span style="color:#B1CD46">1. Create Your Empty Service Repository</span>

To start developing a microservice, create a new Bitbucket repository using the following naming convention:

**Naming Convention**

- _Prefix:_ `pos`
- _Suffix:_ `service`
- Examples:
  - `pos_user_service` (for user management)
  - `pos_payment_service` (for payment handling)

### <span style="color:#B1CD46">2. Clone Your Empty Repository</span>

```bash
git clone https://github.com/your_username/repository_name.git
cd your_project_directory
```

### <span style="color:#B1CD46">3. Setting Up the Virtual Environment</span>

To ensure a clean and isolated environment for your project dependencies, follow these steps to create a virtual environment.

💡 Assuming you are already in the current project directory.

💡 Ensure Python is installed on your system. You can verify this by running python --version (Windows) or python3 --version (macOS/Linux).

### 💻 Windows

1. Create a virtual environment, run: `python -m venv venv`
2. Activate the virtual environment, run: `venv\Scripts\activate`
3. To deactivate the virtual environment, run: `deactivate`

### 💻 macOS / Linux / Git Bash

1. Create a virtual environment, run: `python3 -m venv venv`
2. Activate the virtual environment, run: `source venv/bin/activate`
3. To deactivate the virtual environment, run: `deactivate`

### <span style="color:#B1CD46">4. Install WDG Micro Skeleton</span>

Run the following command to install the Boilerplate:

1.  **Installation**

    ```bash
    pip install git+https://bitbucket.org/wingdev/wdg_micro_skeleton.git
    ```

    This will install the latest version of `wdg_micro_skeleton` along with its required dependencies.

    > Successfully installed wdg_micro_skeleton-0.1.0

2.  **Verify installation, Run**

    ```bash
    pip show wdg_micro_skeleton
    ```

3.  **After installation, Run**

    ```bash
    wdg_micro_skeleton
    ```

    `wdg_micro_skeleton` is a command-line tool that provides a ready-to-use template for setting up a Django-based microservice project. It includes essential configurations, directory structures, and a setup script to help developers quickly initiate their projects with minimal effort.

    The command will print the following instructions:

    > Next steps:
    >
    > 1.  Rename the `configs` folder to match your project name (if needed).
    > 2.  Install your own dependencies: `pip install -r requirements.txt`.
    > 3.  Update `.env` with your environment variables.
    > 4.  Run `python manage.py migrate` to initialize the database.
    >
    > You're ready to start!

4.  **Create a New Django App with WDG Micro Skeleton**

    Use the following command to create a new Django app based on the WDG boilerplate:

    ```bash
    python manage.py create app_name
    ```

    Replace `app_name` with the name of your new app. Running this command will generate a new app structure based on the WDG Micro Skeleton boilerplate. Additionally, it will automatically add the app to the `LOCAL_APPS` section in your Django settings file (base.py).

    > **Note**: If the newly created app encounters an error, please re-check that your app is listed in `LOCAL_APPS` section in your Django settings file (base.py).

5.  **Remove an Existing Django App**

    To remove an app created using the WDG Micro Skeleton, use the following command:

    ```bash
    python manage.py destroy app_name
    ```

    Replace `app_name` with the name of the app you want to remove. This command will completely delete all components associated with the app created in Section 3. Specifically, it will:

    - Remove the app folder and its contents.

    - Automatically update the `LOCAL_APPS` section in the Django settings file (base.py) to remove the app.

    > **Note**: Ensure you have backed up any necessary code or configurations before running this command, as it cannot be undone.

### <span style="color:#B1CD46">5. Uninstall WDG Micro Skeleton</span>

To remove `wdg_micro_skeleton` from your environment, run the following command:

```bash
pip uninstall wdg_micro_skeleton
```

This command will completely uninstall the `wdg_micro_skeleton` package and its related files from your Python environment.

Or you can force reinstall:

```bash
pip install --force-reinstall git+https://bitbucket.org/wingdev/wdg_micro_skeleton.git
```

python manage.py loaddata apps/base/data/factory/countries.json
python manage.py loaddata apps/base/data/factory/res_language.json

##
celery -A config worker -l info --pool=threads --concurrency=5


<div align="center">
    <h3 style="color:#0077FF"><strong style="color:#0077FF">THANK</strong> <strong style="color:#B1CD46">YOU</strong></h3>
    <p>We sincerely appreciate your interest in using the <strong>WDG Micro Skeleton</strong> boilerplate. Your support helps us build efficient and scalable solutions for microservices.
    </p>
    <p>If you have any suggestions, encounter issues, or would like to contribute, please feel free to open an issue or submit a pull request.</p>
    <p>Thank you for being a part of our <strong style="color:#B1CD46">Wing</strong> <strong style="color:#0077FF">Digital</strong> journey! 💡</p>

</div>
