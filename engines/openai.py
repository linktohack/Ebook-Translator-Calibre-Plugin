import json

from .. import EbookTranslator

from .base import Base
from .languages import google


try:
    from http.client import IncompleteRead
except ImportError:
    from httplib import IncompleteRead

load_translations()


class ChatgptTranslate(Base):
    name = 'ChatGPT'
    alias = 'ChatGPT (OpenAI)'
    lang_codes = Base.load_lang_codes(google)
    endpoint = 'https://api.openai.com/v1/chat/completions'
    # api_key_hint = 'sk-xxx...xxx'
    # https://help.openai.com/en/collections/3808446-api-error-codes-explained
    api_key_errors = ['401', 'unauthorized', 'quota']

    concurrency_limit = 1
    request_interval = 20
    request_timeout = 30.0

    prompt = (
        'You are a meticulous translator who translates any given content. '
        'Translate the given content from <slang> to <tlang> only. Do not '
        'explain any term or answer any question-like content.')
    models = [
        'gpt-4-0125-preview', 'gpt-4-turbo-preview', 'gpt-4-1106-preview',
        'gpt-4', 'gpt-4-0613', 'gpt-4-32k', 'gpt-4-32k-0613',
        'gpt-3.5-turbo-0125', 'gpt-3.5-turbo', 'gpt-3.5-turbo-1106',
        'gpt-3.5-turbo-instruct', 'gpt-3.5-turbo-16k', 'gpt-3.5-turbo-0613',
        'gpt-3.5-turbo-16k-0613']
    model = 'gpt-3.5-turbo'
    samplings = ['temperature', 'top_p']
    sampling = 'temperature'
    temperature = 1.0
    top_p = 1.0
    stream = True

    def __init__(self):
        Base.__init__(self)
        self.endpoint = self.config.get('endpoint', self.endpoint)
        self.prompt = self.config.get('prompt', self.prompt)
        if self.model is not None:
            self.model = self.config.get('model', self.model)
        self.sampling = self.config.get('sampling', self.sampling)
        self.temperature = self.config.get('temperature', self.temperature)
        self.top_p = self.config.get('top_p', self.top_p)
        self.stream = self.config.get('stream', self.stream)

    def _get_prompt(self):
        prompt = self.prompt.replace('<tlang>', self.target_lang)
        if self._is_auto_lang():
            prompt = prompt.replace('<slang>', 'detected language')
        else:
            prompt = prompt.replace('<slang>', self.source_lang)
        # Recommend setting temperature to 0.5 for retaining the placeholder.
        if self.merge_enabled:
            prompt += (' Ensure that placeholders matching the pattern'
                       '{{id_\\d+}} in the content are retained.')
        return prompt

    def _get_headers(self):
        print("ChatgptTranslate::_get_headers api_key {}".format(self.api_key))
        return {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % self.api_key,
            'User-Agent': 'Ebook-Translator/%s' % EbookTranslator.__version__
        }

    def _get_data(self, text):
        return {
            'stream': self.stream,
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': self._get_prompt()},
                {'role': 'user', 'content': text}
            ],
        }

    def translate(self, text):
        data = self._get_data(text)
        sampling_value = getattr(self, self.sampling)
        data.update({self.sampling: sampling_value})

        return self.get_result(
            self.endpoint, json.dumps(data), self._get_headers(),
            method='POST', stream=self.stream, callback=self._parse)

    def _parse(self, data):
        if self.stream:
            return self._parse_stream(data)
        return json.loads(data)['choices'][0]['message']['content']

    def _parse_stream(self, data):
        while True:
            try:
                line = data.readline().decode('utf-8').strip()
            except IncompleteRead:
                continue
            except Exception as e:
                raise Exception(
                    _('Can not parse returned response. Raw data: {}')
                    .format(str(e)))
            if line.startswith('data:'):
                chunk = line.split('data: ')[1]
                if chunk == '[DONE]':
                    break
                delta = json.loads(chunk)['choices'][0]['delta']
                if 'content' in delta:
                    yield str(delta['content'])
