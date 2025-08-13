# FireFighter

[![PyPI - Version](https://img.shields.io/pypi/v/firefighter-incident)](https://pypi.org/project/firefighter-incident/) [![PyPI - Python Version](https://img.shields.io/pypi/pyversions/firefighter-incident)](https://pypi.org/project/firefighter-incident/) [![PyPI - License](https://img.shields.io/pypi/l/firefighter-incident)](https://manomanotech.github.io/firefighter-incident/latest/license/) [![OpenSSF Best Practices](https://www.bestpractices.dev/projects/8170/badge)](https://www.bestpractices.dev/projects/8170) [![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

FireFighter is ManoMano's in-house Incident Management Tool.

It helps manage incidents, by automatically creating a Slack channel for communication, and much more.

![Slack Bot Commands](docs/assets/screenshots/slack_bot_home.jpeg)

__What's Incident Management?__

Incident Management is a set of processes and tools to help teams detect, respond to, and resolve incidents quickly and effectively.

Incidents are unplanned interruptions or reductions in quality of services, like a service outage or a security breach.

<!--intro-end-->

## ✨ Recent Updates

### Streamlined Slack Experience (June 2025)

We've improved the incident creation workflow in Slack:

- **🚀 Faster incident creation**: Removed manual Critical/Normal selection step
- **🎯 Automatic process determination**: P1-P3 incidents automatically get Slack channels + Jira tickets, P4-P5 get Jira tickets only
- **✅ Consistent priority handling**: No more mismatches between calculated priority and selected process
- **🧪 Better testing support**: Configurable for test environments without Slack usergroups

The workflow is now: **Select Impacts** → **Auto-calculated Priority & Process** → **Add Details** → **Create Incident**

### System Enhancements Since v0.0.2 (March 2025)

**🏗️ Component & Priority System Overhaul:**
- Complete restructuring of components and groups with 61+ Slack usergroup mappings
- Enhanced P1-P5 priority system with clear Critical/Normal distinction
- Advanced impact level system with business-specific categories
- Automated component-to-usergroup mapping for better response coordination

**🔧 Technical Improvements:**
- Modern Django components with updated type annotations
- Enhanced PDM package management and build processes
- Flexible schema configuration system for customization
- Improved fixture management and testing infrastructure

**📊 Data & Migration:**
- Comprehensive database migrations preserving existing incident data
- CSV-based update system for components and groups
- Enhanced form validation and user interaction flows
- Better business impact calculation algorithms

## Learn more

Check out our [documentation](https://manomanotech.github.io/firefighter-incident/latest/) for more details.

## Contributing

See [our Contribution Guide](https://manomanotech.github.io/firefighter-incident/latest/contributing/) for details on submitting patches, the contribution workflow and developer's guide.

## License

FireFighter is under the MIT license. See the [LICENSE](LICENSE) file for details.
