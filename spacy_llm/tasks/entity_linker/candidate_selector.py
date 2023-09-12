import warnings
from pathlib import Path
from typing import Iterable, Union

import spacy
from spacy.pipeline import EntityLinker
from spacy.tokens import Span

from .ty import EntDescReader, Entity
from .util import UNAVAILABLE_ENTITY_DESC


class PipelineCandidateSelector:
    """Callable generated by loading and wrapping a spaCy pipeline with an EL component and a filled knowledge base."""

    def __init__(
        self,
        nlp_path: Union[Path, str],
        desc_path: Union[Path, str],
        el_component_name: str,
        top_n: int,
        ent_desc_reader: EntDescReader,
    ):
        """
        Loads spaCy pipeline, knowledge base, entity descriptions.
        nlp_path (Union[Path, str]): Path to stored spaCy pipeline.
        desc_path (Union[Path, str]): Path to .csv file with descriptions for entities. Has to have two columns
          with the first one being the entity ID, the second one being the description. The entity ID has to match with
          the entity ID in the stored knowledge base.
        el_component_name (str): EL component name.
        top_n (int): Top n candidates to include in prompt.
        ent_desc_reader (EntDescReader): Entity description reader.
        """
        self._nlp = spacy.load(nlp_path)
        if el_component_name not in self._nlp.component_names:
            raise ValueError(
                f"Component {el_component_name} wasn't found in pipeline {nlp_path}."
            )
        self._entity_linker: EntityLinker = self._nlp.get_pipe(el_component_name)
        self._kb = self._entity_linker.kb
        self._descs = ent_desc_reader(desc_path)
        self._top_n = top_n

    def __call__(self, mentions: Iterable[Span]) -> Iterable[Iterable[Entity]]:
        """Retrieves top n candidates using spaCy's entity linker's .get_candidates_batch().
        mentions (Iterable[Span]): Mentions to look up entity candidates for.
        RETURNS (Iterable[Iterable[Entity]]): Top n entity candidates per mention.
        """
        all_cands = self._kb.get_candidates_batch(mentions)
        for cands in all_cands:
            assert isinstance(cands, list)
            cands.sort(key=lambda x: x.prior_prob, reverse=True)

        return [
            [
                Entity(
                    id=cand.entity_,
                    description=self.get_entity_description(cand.entity_),
                )
                for cand in cands[: self._top_n]
            ]
            if len(cands) > 0
            else [Entity(id=EntityLinker.NIL, description=UNAVAILABLE_ENTITY_DESC)]
            for cands in all_cands
        ]

    def get_entity_description(self, entity_id: str) -> str:
        """Returns entity description for entity ID. If none found, a warning is emitted and
            spacy_llm.tasks.enttiy_linker.util.UNAVAILABLE_ENTITY_DESC is returned.
        entity_id (str): Entity whose ID should be looked up.
        RETURNS (str): Entity description for entity with specfied ID. If no description found, returned string equals
            spacy_llm.tasks.enttiy_linker.util.UNAVAILABLE_ENTITY_DESC.
        """
        if entity_id not in self._descs:
            warnings.warn(
                f"Entity with ID {entity_id} is not in provided descriptions."
            )

        return self._descs.get(entity_id, UNAVAILABLE_ENTITY_DESC)
