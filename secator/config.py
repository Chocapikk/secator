import glob
import os
from pathlib import Path

import yaml
from dotmap import DotMap

from secator.rich import console

DEFAULT_CONFIGS_DIR = os.path.dirname(os.path.abspath(__file__)) + '/configs'
CONFIGS_DIR_KEYS = ['workflows', 'scans', 'profiles']


def load_config(name):
	"""Load a config by name.

	Args:
		name: Name of the config, for instances profiles/aggressive or workflows/domain_scan.

	Returns:
		dict: Loaded config.
	"""
	path = Path(DEFAULT_CONFIGS_DIR) / f'{name}.yaml'
	if not path.exists():
		console.log(f'Config "{name}" could not be loaded.')
		return
	with path.open('r') as f:
		return yaml.load(f.read(), Loader=yaml.Loader)


def find_configs(*dirs):
	results = {}
	for type in CONFIGS_DIR_KEYS:
		default_dir = f'{DEFAULT_CONFIGS_DIR}/{type}'
		dirs_type = [default_dir] + list(dirs)
		paths = []
		for dir in dirs_type:
			dir_paths = [
				os.path.abspath(path)
				for path in glob.glob(dir + '/*.yaml')
			]
			paths.extend(dir_paths)
		results[type] = paths
	return results


class ConfigLoader(DotMap):

	def __init__(self, input={}, name=None, **kwargs):
		if name:
			name = name.replace('-', '_')  # so that workflows have a nice '-' in CLI
			config = self._load_from_name(name)
		elif isinstance(input, str):
			config = self._load_from_file(input)
		else:
			config = input
		super().__init__(config)

	def _load_from_file(self, path):
		if not os.path.exists(path):
			console.log(f'Config path {path} does not exists', style='bold red')
			return
		if path and os.path.exists(path):
			with open(path, 'r') as f:
				return yaml.load(f.read(), Loader=yaml.Loader)

	def _load_from_name(self, name):
		return load_config(name)

	@classmethod
	def load_all(cls):
		configs = find_configs()
		return ConfigLoader({
			key: [ConfigLoader(path) for path in configs[key]]
			for key in CONFIGS_DIR_KEYS
		})

	def get_tasks_class(self):
		from secator.runners import Task
		tasks = []
		for name, conf in self.tasks.items():
			if name == '_group':
				group_conf = ConfigLoader(input={'tasks': conf})
				tasks.extend(group_conf.get_tasks_class())
			else:
				tasks.append(Task.get_task_class(name))
		return tasks

	def get_workflows(self):
		return [ConfigLoader(name=f'workflows/{name}') for name, _ in self.workflows.items()]

	def get_workflow_supported_opts(self):
		opts = {}
		tasks = self.get_tasks_class()
		for task_cls in tasks:
			task_opts = task_cls.get_supported_opts()
			for name, conf in task_opts.items():
				supported = opts.get(name, {}).get('supported', False)
				opts[name] = conf
				opts[name]['supported'] = conf['supported'] or supported
		return opts

	def get_scan_supported_opts(self):
		opts = {}
		workflows = self.get_workflows()
		for workflow in workflows:
			workflow_opts = workflow.get_workflow_supported_opts()
			for name, conf in workflow_opts.items():
				supported = opts.get(name, {}).get('supported', False)
				opts[name] = conf
				opts[name]['supported'] = conf['supported'] or supported
		return opts

	@property
	def supported_opts(self):
		return self.get_supported_opts()

	def get_supported_opts(self):
		opts = {}
		if self.type == 'workflow':
			opts = self.get_workflow_supported_opts()
		elif self.type == 'scan':
			opts = self.get_scan_supported_opts()
		elif self.type == 'task':
			tasks = self.get_tasks_class()
			if tasks:
				opts = tasks[0].get_supported_opts()
		return dict(sorted(opts.items()))