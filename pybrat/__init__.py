import re
import os
import html
import json
import warnings
from copy import deepcopy
from collections import defaultdict
from pathlib import Path
from typing import List


class Annotation(object):
    """
    The base class for brat annotations.
    Use Span, Event, or Attribute instead of this class.
    """
    def __init__(self, _id: str, _type: str, _source_file: str = None):
        assert isinstance(_id, str)
        assert isinstance(_type, str)
        assert isinstance(_source_file, (type(None), str))
        self._id = _id
        self._type = _type
        self._source_file = _source_file
        if _source_file is not None:
            self._source_file = os.path.basename(_source_file)

    @property
    def id(self):
        return self._id

    @property
    def type(self):
        return self._type

    def update(self, key, value):
        self.__dict__[key] = value

    def __eq__(self, other):
        raise NotImplementedError()

    def __hash__(self):
        raise NotImplementedError()

    def __str__(self):
        return self.to_brat_str()

    def __repr__(self):
        field_strings = []
        for (k, v) in self.__dict__.items():
            if k.startswith('_'):
                continue
            if isinstance(v, Annotation):
                v_rep = v.short_repr()
            elif isinstance(v, dict):
                repr_dict = {}
                for (sub_k, sub_v) in v.items():
                    if isinstance(sub_v, Annotation):
                        sub_v_rep = sub_v.short_repr()
                    else:
                        sub_v_rep = repr(sub_v)
                    repr_dict[sub_k] = sub_v_rep
                v_rep = repr(repr_dict)
            elif isinstance(v, (list, tuple)):
                repr_list = []
                for sub_v in v:
                    if isinstance(sub_v, Annotation):
                        sub_v_rep = sub_v.short_repr()
                    else:
                        sub_v_rep = repr(sub_v)
                    repr_list.append(sub_v_rep)
                v_rep = repr(repr_list)
            else:
                v_rep = repr(v)
            field_strings.append(f"{k}: {v_rep}")
        fields_str = ', '.join(field_strings)
        class_name = str(self.__class__).split('.')[-1][:-2]
        rep = f"{class_name}({fields_str})"
        return rep

    def short_repr(self):
        class_name = str(self.__class__).split('.')[-1][:-2]
        contents = [f"id: {self.id})"]
        if "_type" in self.__dict__:
            contents.insert(0, f"type: {self.type}")
        contents_str = ', '.join(contents)
        return f"{class_name}({contents_str})"

    def copy(self):
        """
        Performs a deep copy of this annotation.
        """
        return deepcopy(self)

    @staticmethod
    def _resolve_file_path(path):
        try:
            here = Path(path).resolve()
            abspath = str(here.absolute())
        except TypeError:
            abspath = path
        return abspath

    def to_brat_str(self):
        raise NotImplementedError()


class CharacterIndex(object):
    """
    :param list(tuple) sorted_spans: a list of tuples, each tuple containing
                                     the (start, end) indices of a text span.
    """

    def __init__(self, sorted_spans):
        self.sorted_spans = sorted_spans

    @property
    def start_index(self):
        if len(self.sorted_spans) > 0:
            return self.sorted_spans[0][0]
        return 0

    @property
    def end_index(self):
        if len(self.sorted_spans) > 0:
            return self.sorted_spans[-1][-1]
        return 0

    def __eq__(self, other):
        if not isinstance(other, CharacterIndex):
            return False
        return all([self_span == other_span for (self_span, other_span)
                    in zip(self.sorted_spans, other.sorted_spans)])

    def __iter__(self):
        return iter([idx for span in self.sorted_spans
                     for idx in range(*span)])

    def __add__(self, other):
        if not isinstance(other, CharacterIndex):
            raise TypeError("other element must be CharacterIndex.")
        spans = self.sorted_spans + other.sorted_spans
        return CharacterIndex(spans)

    def __hash__(self):
        return hash(str(self.sorted_spans))

    def __str__(self):
        return ';'.join([f"{span[0]} {span[1]}" for span in self.sorted_spans])

    def __repr__(self):
        return f"CharacterIndex({str(self.sorted_spans)})"


class Span(Annotation):
    """
    A brat span. I.e., a span of text.

    :param str _id: the unique numerical identifier of this span with the 'T'
                    prefix. E.g., 'T3'.
    :param CharacterIndex indices: the CharacterIndex for this span.
    :param str text: the actual span text
    :param str _type: (Optional) a string giving the type of this span,
                      e.g., for NER. Default is 'Span'.
    :param str _source_file: (Optional), the name of the .ann file which
                             contains this span.
    """
    def __init__(self, _id: str, indices: CharacterIndex,
                 text: str, _type: str = "Span", _source_file: str = None,
                 attributes=None):
        super().__init__(_id=_id, _type=_type, _source_file=_source_file)
        assert isinstance(indices, CharacterIndex)
        assert isinstance(text, str)
        self.indices = indices
        self.text = text
        self.attributes = {}
        attributes = attributes or {}
        for attr in attributes.values():
            attr.reference = self
        self.attributes = attributes

    @property
    def start_index(self):
        return self.indices.start_index

    @property
    def end_index(self):
        return self.indices.end_index

    def __eq__(self, other):
        if not isinstance(other, Span):
            return False
        return all([
            self.type == other.type,
            self.indices == other.indices,
            self.text == other.text,
        ])

    def __hash__(self):
        return hash((
            self.type,
            self.indices,
            self.text,
        ))

    def to_brat_str(self, output_references=False, seen=None):
        """
        Format this Event instance as a brat string.

        :param bool output_references: If True, also includes the brat string
            of the Spans and Attributes of this Event. Default False.
        """
        if seen is None:
            seen = set()
        if self.id in seen:
            return ''
        seen.add(self.id)
        span_str = f"{self.id}\t{self.type} {str(self.indices)}\t{self.text}"  # noqa
        outlines = [span_str]
        if output_references is True:
            attr_strs = [a.to_brat_str(output_references=False, seen=seen)
                         for a in self.attributes.values()]
            attr_strs = [s for s in attr_strs if s != '']
            outlines.extend(attr_strs)
        brat_str = '\n'.join(outlines)
        return brat_str

    def asdict(self):
        return {'_id': self.id,
                '_type': self.type,
                'indices': str(self.indices),
                'text': self.text,
                '_source_file': self._source_file}


class Attribute(Annotation):
    """
    A brat attribute. Can be attached to Spans or Events.

    :param str _id: the unique numerical identifier of this attribute with
                    the 'A' prefix. E.g., 'A5'.
    :param Any value: the value of this attribute.
    :param Annotation reference: the corresponding Span or Event instance.
    :param str _type: (Optional) a string giving the type of this attribute.
                      Default is 'Attribute'.
    :param str _source_file: (Optional), the name of the .ann file which
                             contains this span.
    """
    def __init__(self, _id, value, reference=None,
                 _type="Attribute", _source_file=None):
        super().__init__(_id=_id, _type=_type, _source_file=_source_file)
        assert isinstance(reference, (type(None), Annotation))
        self.value = value
        self.reference = reference
        if not isinstance(self.reference, (Span, Event, type(None))):
            raise ValueError(f"Attribute reference must be instance of Span, Event, or None. Got {type(self.reference)}.")  # noqa
        # Add this attribute to the reference annotation
        if isinstance(self.reference, (Span, Event)):
            self.reference.attributes[self._type] = self

    def __eq__(self, other):
        if not isinstance(other, Attribute):
            return False
        return all([
            self.type == other.type,
            self.value == other.value,
            # Attributes and events can point to each
            # other, so we'll use IDs to avoid endless recursion.
            self.reference.id == other.reference.id,
        ])

    def __hash__(self):
        return hash((
            self.type,
            self.value,
            self.reference.id,
        ))

    @property
    def span(self):
        if self.reference is None:
            span = None
        elif isinstance(self.reference, Span):
            span = self.reference
        elif isinstance(self.reference, Event):
            span = self.reference.spans
        else:
            raise ValueError(f"reference must be Span, Event, or None. Got {type(self.reference)}.")  # noqa
        return span

    @property
    def start_index(self):
        """
        The starting character index of this Attribute's reference.
        """
        return self.span.start_index

    @property
    def end_index(self):
        """
        The ending character index of this Attribute's reference.
        """
        return self.span.end_index

    @property
    def indices(self):
        return self.span.indices

    def to_brat_str(self, output_references=False, seen=None):
        """
        Format this Attribute instance as a brat string.

        :param bool output_references: If True, also includes the brat string
            of the reference of this Attribute. Default False.
        """
        if seen is None:
            seen = set()
        if self.id in seen:
            return ''
        seen.add(self.id)
        outlines = []
        if output_references is True:
            if self.reference is not None:
                ref_str = self.reference.to_brat_str(output_references=False,
                                                     seen=seen)
                if ref_str != '':
                    outlines.append(ref_str)
        ref_id = self.reference.id
        outlines.append(f"{self.id}\t{self.type} {ref_id} {self.value}")
        return '\n'.join(outlines)

    def asdict(self):
        return {'_id': self.id,
                '_type': self.type,
                'value': self.value,
                'ref_id': self.reference.id,
                '_source_file': self._source_file}


class Event(Annotation):
    """
    A brat event, composed of one or more ordered Span instances.
    pybrat does not enforce any specific Event structure.

    :param str _id: the unique numerical identifier of this event
                    with the E prefix. E.g., 'E10'.
    :param Span spans: one or more Span instances.
    :param dict attributes: a dictionary of Attribute instances
                            keyed by attribute type.
    :param str _type: (Optional) A type for this Event. Default is 'Event'.
    :param str _source_file: (Optional), the name of the .ann file which
                             contains this span.
    """
    def __init__(self, _id, *spans, attributes=None,
                 _type="Event", _source_file=None):
        super().__init__(_id=_id, _type=_type, _source_file=_source_file)
        for span in spans:
            assert isinstance(span, (Span, Event)), f"Not a Span instance: {span}"  # noqa
        self.spans = spans
        self.attributes = attributes or {}
        for attr in self.attributes.values():
            attr.reference = self

    def __eq__(self, other):
        if not isinstance(other, Event):
            return False
        return all([
            self.spans == other.spans,
            self.attributes == other.attributes,
        ])

    def __hash__(self):
        return hash((self.type, self.spans))

    @property
    def start_index(self):
        """
        The lowest character index of this Event's spans.
        """
        return min([span.start_index for span in self.spans])

    @property
    def end_index(self):
        """
        The highest character index of this Event's spans.
        """
        return max([span.end_index for span in self.spans])

    @property
    def indices(self):
        return sum([span.indices for span in self.spans], CharacterIndex([]))

    def to_brat_str(self, output_references=False, seen=None):
        """
        Format this Event instance as a brat string.

        :param bool output_references: If True, also includes the brat string
            of the Spans and Attributes of this Event. Default False.
        """
        if seen is None:
            seen = set()
        if self.id in seen:
            return ''
        seen.add(self.id)
        event_str = f"{self.id}\t"
        for (i, span) in enumerate(self.spans):
            spantype = span.type
            if i == 0:
                spantype = self.type
            event_str += f"{spantype}:{span.id} "
        outlines = [event_str.strip()]
        if output_references is True:
            attr_strs = [a.to_brat_str(output_references=False, seen=seen)
                         for a in self.attributes.values()]
            attr_strs = [s for s in attr_strs if s != '']
            outlines.extend(attr_strs)
            for span in self.spans[::-1]:
                span_str = span.to_brat_str(output_references=True, seen=seen)
                if span_str != '':
                    outlines.insert(0, span_str)
        brat_str = '\n'.join(outlines)
        return brat_str

    def asdict(self):
        return {'_id': self.id,
                '_type': self.type,
                'ref_spans': [(ref.type, ref.id) for ref in self.spans],
                '_source_file': self._source_file}


class BratAnnotations(object):
    """
    The main class for working with brat annotations.

    You can read annotations from a file.

    .. code-block:: python

        >>> import pybrat
        >>> anns = pybrat.BratAnnotations.from_file("path/to/file.ann")

    You can also create a set of annotations from Event instances.

    .. code-block:: python

        >>> import pybrat
        >>> event1 = pybrat.Event("E1", *e1spans)
        >>> event2 = pybrat.Event("E2", *e2spans)
        >>> anns = pybrat.BratAnnotations.from_events([event1, event2])
    """

    @classmethod
    def from_file(cls, fpath):
        """
        Read brat annotations from the specified file.

        :param str fpath: The path to the ann file.
        :returns: a new BratAnnotations instance.
        """
        spans = []
        events = []
        attributes = []
        source_file = fpath
        with open(fpath, 'r') as inF:
            for line in inF:
                line = line.strip()
                ann_type = line[0]
                if ann_type == 'T':
                    data = parse_brat_span(line)
                    data["_source_file"] = fpath
                    spans.append(data)
                elif ann_type == 'E':
                    data = parse_brat_event(line)
                    data["_source_file"] = fpath
                    events.append(data)
                elif ann_type == 'A':
                    data = parse_brat_attribute(line)
                    data["_source_file"] = fpath
                    attributes.append(data)
                else:
                    raise ValueError(f"Unsupported ann_type '{ann_type}'.")
        annotations = cls(spans=spans, events=events, attributes=attributes,
                          _source_file=source_file)
        return annotations

    @classmethod
    def from_events(cls, events_iter):
        """
        Create a BratAnnotations instance from a collection of Events.
        Assumes that the Event instances in events_iter contain all Spans
        and Attributes.

        :param List[Event] events_iter: An iterable over Event instances.
        """
        annotations = cls(spans=[], events=[], attributes=[])
        annotations._events = list(events_iter)
        for event in annotations.events:
            annotations._attributes.extend(event.attributes.values())
            for span in event.spans:
                annotations._spans.append(span)
                annotations._attributes.extend(span.attributes.values())
        return annotations

    def __init__(self, spans=None, events=None, attributes=None,
                 _source_file=None):
        self._raw_spans = spans or []
        self._raw_events = events or []
        self._raw_attributes = attributes or []
        self._spans = []  # Will hold Span instances
        self._attributes = []  # Will hold Attribute instances
        self._events = []  # Will hold Event instances
        self._source_file = _source_file
        self._resolve()
        self._sorted_spans = None
        self._sorted_attributes = None
        self._sorted_events = None

    def __eq__(self, other):
        if not isinstance(other, BratAnnotations):
            print("diff type")
            return False
        if len(self.spans) != len(other.spans):
            print("diff len spans")
            return False
        for (this_span, other_span) in zip(self.spans, other.spans):
            if this_span != other_span:
                print(f"{this_span} != {other_span}")
                return False
        if len(self.attributes) != len(other.attributes):
            print("diff len attrs")
            return False
        for (this_attr, other_attr) in zip(self.attributes, other.attributes):
            if this_attr != other_attr:
                print(f"{this_attr} != {other_attr}")
                return False
        if len(self.events) != len(other.events):
            print("diff len events")
            return False
        for (this_event, other_event) in zip(self.events, other.events):
            if this_event != other_event:
                print(f"{this_event} != {other_event}")
                return False
        return True

    def get_events_by_type(self, event_type):
        return [e for e in self.events if e.type == event_type]

    def get_attributes_by_type(self, attr_type):
        return [a for a in self.attributes if a.type == attr_type]

    def get_spans_by_type(self, span_type):
        return [s for s in self.spans if s.type == span_type]

    @property
    def spans(self):
        return self._sort_spans_by_index()

    @property
    def attributes(self):
        return self._sort_attributes_by_span_index()

    @property
    def events(self):
        return self._sort_events_by_span_index()

    def __iter__(self):
        for ann in self.get_highest_level_annotations():
            yield ann

    def _sort_spans_by_index(self):
        return sorted(self._spans, key=lambda s: s.start_index)

    def _sort_attributes_by_span_index(self):
        # An Attribute may refer to a Span or an Event,
        # so we have to check which is the case. If its an Event,
        # we have to sort by the Event.span
        span_indices_types = []
        for attr in self._attributes:
            # Use 'A' and 'B' so that spans come first in the sort order, given
            # the same start_index.
            if isinstance(attr.reference, Span):
                span_indices_types.append((attr.reference.start_index, 'A'))
            elif isinstance(attr.reference, Event):
                span_indices_types.append((attr.reference.start_index, 'B'))
        sorted_indices = sorted(enumerate(span_indices_types),
                                key=lambda s: s[1])
        sorted_indices = [i for (i, (idx, _)) in sorted_indices]
        return [self._attributes[i] for i in sorted_indices]

    def _sort_events_by_span_index(self):
        return sorted(self._events, key=lambda e: e.start_index)

    def _resolve(self):
        """
        Given a set of raw spans, attributes, and events, e.g., as read
        from a .ann file, creates Span, Attribute, and Event instances and
        then links them as specified in the file.
        """
        span_lookup = {}
        event_lookup = {}
        attribute_lookup = defaultdict(list)

        for raw_span in self._raw_spans:
            if "_source_file" in raw_span:
                if self._source_file is None:
                    self._source_file = raw_span["_source_file"]
                else:
                    if self._source_file != raw_span["_source_file"]:
                        raise OSError(f"Found conflicting source files! {self._source_file} != {raw_span['source_file']}")  # noqa
            span = Span(**raw_span)
            span_lookup[raw_span["_id"]] = span
            self._spans.append(span)

        for raw_attr in self._raw_attributes:
            if "_source_file" in raw_attr:
                if self._source_file != raw_attr["_source_file"]:
                    raise OSError(f"Found conflicting source files! {self._source_file} != {raw_attr['source_file']}")  # noqa
            ref_id = raw_attr.pop("ref_id")
            ref = span_lookup.get(ref_id, None)
            attribute = Attribute(**raw_attr, reference=ref)
            attribute_lookup[ref_id].append(attribute)
            self._attributes.append(attribute)

        # Events can be nested, and sometimes can be out of order,
        # so we loop over the raw events until they're all accounted for.
        while len(event_lookup) < len(self._raw_events):
            for raw_event in self._raw_events:
                if raw_event["_id"] in event_lookup.keys():
                    continue
                if "_source_file" in raw_event:
                    if self._source_file != raw_event["_source_file"]:
                        raise OSError(f"Found conflicting source files! {self._source_file} != {raw_event['source_file']}")  # noqa
                event_spans = []
                skip_this_event = False
                for (span_type, span_id) in raw_event["ref_spans"]:
                    try:
                        span = span_lookup[span_id]
                    except KeyError:
                        try:
                            span = event_lookup[span_id]
                        except KeyError:
                            skip_this_event = True
                            break
                    event_spans.append(span)
                if skip_this_event is True:
                    continue

                event = Event(raw_event["_id"], _type=raw_event["_type"],
                              *event_spans, attributes=None,
                              _source_file=raw_event["_source_file"])
                event_lookup[raw_event["_id"]] = event
                attrs = attribute_lookup[raw_event["_id"]]
                for attr in attrs:
                    attr.reference = event
                attrs_by_type = {attr.type: attr for attr in attrs}
                event.attributes = attrs_by_type
                self._events.append(event)

    def get_highest_level_annotations(self, type=None):
        """
        brat annotations can include only spans, spans + events,
        or spans + events + attributes. This method allows one to
        get the highest-level annotation available in this file.

        In order from highest to lowest level:
          Event
          Attribute
          Span

        :param str type: (Optional) return annotations with the specified type.
        """
        if len(self._events) > 0:
            if type is not None:
                return self.get_events_by_type(type)
            else:
                return self.events
        elif len(self._spans) > 0:
            if type is not None:
                return self.get_spans_by_type(type)
            else:
                return self.spans
        elif len(self._attributes) > 0:
            if type is not None:
                return self.get_attributes_by_type(type)
            else:
                return self.attributes
        else:
            return []

    def __str__(self):
        seen_spans = set()
        seen_attrs = set()
        brat_str = ''
        seen = set()
        for event in self.events:
            line = event.to_brat_str(output_references=True, seen=seen)
            if line != '':
                brat_str += line + '\n'
            seen_spans.update(event.spans)
            seen_attrs.update(event.attributes.values())
        for span in self.spans:
            if span not in seen_spans:
                line = span.to_brat_str(output_references=True, seen=seen)
                if line != '':
                    brat_str += line + '\n'
                seen_attrs.update(span.attributes.values())
        for attr in self.attributes:
            if attr not in seen_attrs:
                line = attr.to_brat_str(output_references=False, seen=seen)
                if line != '':
                    brat_str += line + '\n'
        return brat_str.strip()

    def add_annotation(self, annotation: Annotation):
        ann_cls = annotation.__class__.__name__
        references = []

        if ann_cls == "Span":
            annlist = self._spans
            prefix = 'T'
        elif ann_cls == "Event":
            annlist = self._events
            prefix = 'E'
            references = annotation.spans
        elif ann_cls == "Attribute":
            annlist = self._attributes
            prefix = 'A'
            references = [annotation.reference]
        else:
            raise ValueError(f"Unsupported Annotation type '{ann_cls}'")
        if annotation in annlist:
            return
        seen_ids = set([ann.id for ann in annlist])
        if annotation.id in seen_ids:
            max_id = max([int(annid.strip(prefix)) for annid in seen_ids])
            annotation._id = f"{prefix}{max_id + 1}"
        annlist.append(annotation)
        for ref in references:
            self.add_annotation(ref)

    def save_brat(self, outdir, filename=None):
        """
        Save these brat annotations to a brat-formatted file.

        :param str outdir: The directory in which to save the file.
        :param str filename: (Optional) The filename to use. If not specified,
                             attempts to use the Annotation._source_file.
        """
        if filename is None and self._source_file is None:
            raise ValueError("No filename specified.")
        if filename is not None:
            outfile = os.path.join(outdir, filename)
        else:
            bn = os.path.basename(self._source_file)
            outfile = os.path.join(outdir, bn)
        brat_str = str(self)
        with open(outfile, 'a') as outF:
            outF.write(brat_str + '\n')


class BratText(object):
    """
    A simple class for organizing the text that corresponds to a
    file of brat annotations.

    Specify plain text, split sentences, or both.

    .. code-block:: python

        >>> bt = BratText(text=plain_text, sentences=list_of_sents)
        >>> bt.text(0, 12)  # Plain text at character indices 0 through 12
        >>> bt.tokens(0, 12)  # Tokens spanning character indices 0 through 12
        >>> bt.sentences(0, 12)  # Sentences spanning character indices 0 - 12

    `sentences` can also be a json lines file with the following format:

    .. code-block:: bash

        {"sent_index": int  # the number of this sentence in the document
         "start_char": int  # the character offset of the start of the sentence
         "end_char": int    # the character offset of the end of the sentence
         "_text":           # the sentence text
        }

    You can also access the text using Annotation instances

    .. code-block:: python

        >>> anns = BratAnnotations.from_file("path/to/file1.ann")
        >>> bt = BratText.from_files(text="path/to/file1.txt",
        ...                          sentences="path/to/file1.jsonl")
        >>> # get the text of the first span
        >>> bt.text(annotations=[anns.spans[0]])
        >>> # tokens from the first three spans
        >>> bt.tokens(annotations=anns.spans[0:3])
        >>> # Sentences containing all events
        >>> bt.sentences(annotations=anns.events[:])
    """
    @classmethod
    def from_files(cls, text=None, sentences=None, tokenizer=None):
        if text is None and sentences is None:
            raise ValueError("Must specify at least one of text, sentences")
        if text is not None:
            text = open(text, 'r').read()
        if sentences is not None:
            try:
                sentences = [json.loads(line) for line in open(sentences, 'r')]
            except json.JSONDecodeError:
                sentences = open(sentences, 'r').readlines()
        return cls(text=text, sentences=sentences, tokenizer=tokenizer)

    def __init__(self, text=None, sentences=None, tokenizer=None):
        if text is None and sentences is None:
            raise ValueError("Must supply at least one of text or sentences")
        self.is_split_into_sentences = sentences is not None
        if sentences is not None:
            self._sentences_lookup = self._split_sentences(sentences)
        if text is None:
            self._text = self._get_text_from_sentences()
        else:
            self._text = text
        self.tokenizer = self._get_tokenizer(tokenizer)
        self._tokens = None
        self._tokens_lookup = self._tokenize(self._text)

    def __str__(self):
        return self._text

    def text(self, annotations: List[Annotation] = [],
             start_char: int = None, end_char: int = None):
        assert isinstance(start_char, (type(None), int))
        assert isinstance(end_char, (type(None), int))
        if not isinstance(annotations, list):
            annotations = [annotations]
        assert all([isinstance(ann, Annotation) for ann in annotations])
        if len(annotations) > 0:
            if start_char is not None or end_char is not None:
                warnings.warn("Ignoring {start,end}_char since Annotation was provided.")  # noqa
            start_char = min([ann.start_index for ann in annotations])
            end_char = max([ann.end_index for ann in annotations])
        if end_char is None:
            if start_char is None:
                end_char = len(self._text)
            else:
                end_char = start_char + 1
        if start_char is None:
            start_char = 0
        return self._text[start_char:end_char]

    def tokens(self, annotations: List[Annotation] = [],
               start_char: int = None, end_char: int = None):
        assert isinstance(start_char, (type(None), int))
        assert isinstance(end_char, (type(None), int))
        if not isinstance(annotations, list):
            annotations = [annotations]
        assert all([isinstance(ann, Annotation) for ann in annotations])
        if len(annotations) > 0:
            if start_char is not None or end_char is not None:
                warnings.warn("Ignoring {start,end}_char since Annotation was provided.")  # noqa
            char_idxs = sum([ann.indices for ann in annotations],
                            CharacterIndex([]))

        else:
            if end_char is None:
                if start_char is None:
                    end_char = len(self._text)
                else:
                    end_char = start_char + 1
            if start_char is None:
                start_char = 0
            char_idxs = range(start_char, end_char)

        tokens = []
        for char_i in char_idxs:
            try:
                t = self._tokens_lookup[char_i]
            except KeyError:
                continue
            if len(tokens) == 0 or t != tokens[-1]:
                tokens.append(t)
        return tokens

    def sentences(self, annotations: List[Annotation] = [],
                  start_char: int = None, end_char: int = None):
        if self.is_split_into_sentences is False:
            raise ValueError("Text is not split into sentences.")
        assert isinstance(start_char, (type(None), int))
        assert isinstance(end_char, (type(None), int))
        if not isinstance(annotations, list):
            annotations = [annotations]
        assert all([isinstance(ann, Annotation) for ann in annotations])
        if len(annotations) > 0:
            if start_char is not None or end_char is not None:
                warnings.warn("Ignoring {start,end}_char since Annotation was provided.")  # noqa
            char_idxs = sum([ann.indices for ann in annotations],
                            CharacterIndex([]))
        else:
            if end_char is None:
                if start_char is None:
                    end_char = max(list(self._sentences_lookup.keys()))
                else:
                    end_char = start_char + 1
            if start_char is None:
                start_char = min(list(self._sentences_lookup.keys()))
            char_idxs = range(start_char, end_char)

        sents = []
        for char_i in char_idxs:
            try:
                s = self._sentences_lookup[char_i]
            except KeyError:
                continue
            if s not in sents:
                sents.append(s)
        return sents

    def save(self, outdir, filename=None):
        """
        Save this BratText instance to a plain text file.

        :param str outdir: The directory in which to save the file.
        :param str filename: (Optional) The filename to use. If not specified,
                             attempts to use the Annotation._source_file.
        """
        if filename is None and self._source_file is None:
            raise ValueError("No filename specified.")
        if filename is not None:
            outfile = os.path.join(outdir, filename)
        else:
            bn = os.path.basename(self._source_file)
            outfile = os.path.join(outdir, bn)
        brat_str = str(self)
        with open(outfile, 'a') as outF:
            outF.write(brat_str + '\n')

    def _get_text_from_sentences(self):
        text = ''
        for sent in self.sentences():
            text += ' ' * (sent["start_char"] - len(text))
            text += sent["_text"]
        return text

    def _split_sentences(self, sentences):
        assert isinstance(sentences, list)
        is_str = all([isinstance(sent, str) for sent in sentences])
        is_dict = all([isinstance(sent, dict) for sent in sentences])
        assert is_str or is_dict

        sentence_lookup = {}
        if is_str:
            # assume sentences passed in order with no character offsets
            current_start = 0
            for (i, sent) in enumerate(sentences):
                current_end = current_start + len(sent)
                sent_data = {"sent_index": i,
                             "start_char": current_start,
                             "end_char": current_end,
                             "_text": sent}
                for char_idx in range(current_start, current_end):
                    sentence_lookup[char_idx] = sent_data
                current_start = current_end
        elif is_dict:
            seen_indices = set()
            for sent in sentences:
                assert "sent_index" in sent
                assert "start_char" in sent
                assert "end_char" in sent
                assert "_text" in sent
                assert sent["sent_index"] not in seen_indices, "Duplicate sent_index!"  # noqa
                seen_indices.add(sent["sent_index"])
                for char_idx in range(sent["start_char"], sent["end_char"]):
                    sentence_lookup[char_idx] = sent
        return sentence_lookup

    def _get_tokenizer(self, tokenizer):
        if tokenizer is None:
            tokenizer = RegexTokenizer()
        return tokenizer

    def _tokenize(self, text):
        tokens, char_ranges = self.tokenizer(text)
        token_lookup = {}
        for (tok, crange) in zip(tokens, char_ranges):
            for ci in range(*crange):
                token_lookup[ci] = tok
        return token_lookup


class RegexTokenizer(object):
    """
    A very simple tokenizer that splits on whitespace by default.

    .. code-block:: python

        >>> import pybrat
        >>> tokenizer = pybrat.RegexTokenizer()
        >>> text = "The cat in the hat"
        >>> tokens, token_char_ranges = tokenizer(text)
    """
    def __init__(self, split_pattern=r'\s'):
        self.split_pattern = re.compile(split_pattern)

    def __call__(self, text: str):
        tokens = []
        token_char_idxs = []
        current_text = ''
        current_char_idxs = []
        for (i, char) in enumerate(text):
            if self.split_pattern.match(char):
                if len(current_text) > 0:
                    tokens.append(current_text)
                    token_char_idxs.append(current_char_idxs)
                current_text = ''
                current_char_idxs = []
            else:
                current_text += char
                current_char_idxs.append(i)
        if len(current_text) > 0:
            tokens.append(current_text)
            token_char_idxs.append(current_char_idxs)
        token_ranges = [(char_idxs[0], char_idxs[-1])
                        for char_idxs in token_char_idxs]
        return tokens, token_ranges


def parse_brat_span(line):
    # Sometimes things like '&quot;' appear
    line = html.unescape(line)
    uid, label, other = line.split(maxsplit=2)
    # start1 end1;start2 end2
    tmp = other.split('\t')
    if len(tmp) == 1:
        spans = tmp[0]
        text = ''
    else:
        spans, text = tmp
    if ';' in spans:
        spans = [s.split() for s in spans.split(';')]
        spans = [(int(s), int(e)) for (s, e) in spans]
        indices = CharacterIndex(spans)
    else:
        s, e = spans.split()
        indices = CharacterIndex([(int(s), int(e))])

    return {"_id": uid,
            "_type": label,
            "indices": indices,
            "text": text}


def parse_brat_event(line):
    fields = line.split('\t')
    if len(fields) > 2:
        # Sometimes we get attributes appended to the end
        # E0\tSubject:T0 Object:T1\tSource:T001
        # Ignore with warning for now
        warnings.warn(f"Ignoring extra data {fields[2:]} for event {fields[0]}")  # noqa
        fields = fields[:2]
    uid = fields[0]
    spans_str = fields[1]
    spans = spans_str.split()
    # There should be at least one span
    assert len(spans) >= 1
    ref_spans = []
    event_label = None
    for (i, span) in enumerate(spans):
        label, ref = span.split(':')
        ref_spans.append((label, ref))
        if i == 0:
            event_label = label
    return {"_id": uid,
            "_type": event_label,
            "ref_spans": ref_spans}


def parse_brat_attribute(line):
    fields = line.split()
    if fields[1] == "Negation":
        if len(fields) == 3:
            fields.append("Negated")
    assert len(fields) == 4
    uid, label, ref, value = fields
    return {"_id": uid,
            "_type": label,
            "value": value,
            "ref_id": ref}
