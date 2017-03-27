#! /usr/bin/env python3

import random

from .eventsignal import Signal
from .feature import Promoter, Terminator, Mask
from .choices import weighted_choice


class Polymer:
    """
    Track element objects, polymerase objects, and collisions on a single
    polymer. Move polymerase objects along the polymer. Handle logic for
    covering and uncovering of elements. This class contains the core of the
    single-moleculre tracking used for both genomes (transcription) and
    transcripts (translation).

    The terms polymer, polymerase, promoter, and terminator are all used
    generically in this class. Each term could refer to a different biological
    definition in the context of transcription and translation.

    * polymer: genome, transcript
    * polymerase: RNA polymerase, ribosome, any object that binds to polymer
    * promoter: promoter, ribosome binding site, any site on a polymer in which
        a protein (polymerase) can bind
    * terminator: terminator, stop codon, any site on polymer that ends
        polymerization

    """
    def __init__(self, name, start, stop, elements, mask):
        """
        :param name: name of this polymer (should it be unique?)
        :param length: length of polymer (used purely for debugging, may not be
            needed)
        :param elements: all elements on this polymer, including promoters,
            terminators, etc.
        :param mask: mask object which determines which portions of the polymer
            are currently inaccessible
        """
        self.index = 0
        self.name = name
        self.start = start
        self.stop = stop
        self.polymerases = []
        self.elements = elements
        self.termination_signal = Signal()  # Fires on termination
        self.propensity_signal = Signal()  # Fires when propensity changes
        self.mask = mask
        self.prop_sum = 0
        self.prop_list = []
        self.uncovered = {}  # Running count of free promoters

        # Cover masked elements
        for element in self.elements:
            element.cover_signal.connect(self.cover_element)
            element.uncover_signal.connect(self.uncover_element)
            if self.elements_intersect(element, self.mask):
                element.cover()
                element.save_state()
                if element.name not in self.uncovered:
                    self.uncovered[element.name] = 0
            else:
                if element.name not in self.uncovered:
                    self.uncovered[element.name] = 1
                else:
                    self.uncovered[element.name] += 1

    def bind_polymerase(self, pol, promoter):
        """
        Bind a polymerase object to the polymer. Randomly select an open
        promoter with which to bind and update the polymerases position to the
        position of that promoter.

        :param pol: polymerase object.
        :param promoter: the name of a promoter that pol will bind

        """
        found = False
        element_choices = []
        # Make list of free promoters that pol can bind
        for element in self.elements:
            if element.name == promoter and not element.is_covered():
                element_choices.append(element)
                found = True

        if found is False:
            raise RuntimeError("Polymerase '{0}' could not find free "
                               "promoter '{1}' to bind to in polymer"
                               " '{2}'."
                               .format(pol.name, promoter, self.name))

        # Randomly select promoter
        element = weighted_choice(element_choices)

        if not element.check_interaction(pol.name):
            raise RuntimeError("Polymerase '{0}' does not interact with "
                               "promoter '{1}'."
                               .format(pol.name, promoter))

        # Update polymerase coordinates
        pol.start = element.start
        pol.stop = element.start + pol.footprint - 1
        pol.left_most_element = self.elements.index(element)

        if element.stop < pol.stop:
            raise RuntimeError("Polymerase '{0}' footprint is larger than "
                               "that of promoter '{1}' it is binding to. This "
                               "could cause unexpected behavior."
                               .format(pol.name, promoter))
        if pol.stop > self.mask.start:
            raise RuntimeError("Polymerase '{0}' will overlap with mask "
                               "upon promoter binding. This may "
                               "cause the polymerase to stall and "
                               "produce unexpected behavior."
                               .format(pol.name))
        # Cover promoter
        element.cover()
        element.save_state()
        self.uncovered[element.name] -= 1
        assert element._covered == element._old_covered
        assert self.uncovered[element.name] > -1
        # Add polymerase to tracked-polymerases list
        # Polymerases are maintained in order, such that higher-index
        # polymerases have moved further along the DNA
        # This make collision detection very efficient
        self._insert_polymerase(pol)
        # Update total move propensity for this polymer
        self.prop_sum += pol.speed
        self.propensity_signal.fire()

    def execute(self):
        """
        Select a polymerase to move next and deal with terminations.
        """
        if self.prop_sum == 0:
            raise RuntimeError("Attempting to execute polymer '{0}' with a "
                               "reaction propensity of 0.".format(self.name))
        # Randomly choose polymerase to move
        pol = self._choose_polymerase()
        self._move_polymerase(pol)

    def shift_mask(self):
        """
        Shift start of mask by 1 base-pair and check for uncovered elements.
        """
        # Check to see that mask still has some width
        if self.mask.start >= self.mask.stop:
            return

        index = -1
        for i, element in enumerate(self.elements):
            if self.elements_intersect(self.mask, element):
                element.save_state()
                element.uncover()
                index = i
                break

        self.mask.recede()

        if index == -1:
            return
        # Re-cover masked elements
        if self.elements_intersect(self.mask, self.elements[index]):
            self.elements[index].cover()
        # Check for just-uncovered elements
        # self._check_state(self.elements[index])
        self.elements[index].check_state()
        self.elements[index].save_state()

    def terminate(self, pol, element_stop, element_gene=""):
        self.prop_sum -= pol.speed
        pol.release_signal.fire(element_stop)
        index = self.polymerases.index(pol)
        self.propensity_signal.fire()
        del self.polymerases[index]
        del self.prop_list[index]

    def count_uncovered(self, species):
        """
        Count the number of free promoters that match name `species`.

        :param species: name of promoter to count
        """
        return self.uncovered[species]

    def cover_element(self, species):
        self.uncovered[species] -= 1

    def uncover_element(self, species):
        self.uncovered[species] += 1

    def calculate_propensity(self):
        """
        Calculate the total propensity of all polymerase movement in this
        polymer.

        :returns: total propensity
        """
        return self.prop_sum

    def _insert_polymerase(self, pol):
        """
        Add a polymerase to polymerase list, while maintaining the
        order in which polymerases currently on the polymer. Higher
        indices correspond to downstream polymerases, and lower
        indices correspond to upstream polymerases.

        :param pol: polymerase object
        """
        if pol in self.polymerases:
            raise RuntimeError("Polymerase '{0}' is already present on polymer"
                               " '{1}'.".format(pol.name, self.name)
                               )
        found_position = False
        insert_position = 0
        for index, old_pol in enumerate(self.polymerases):
            # Find the first polymerase that is
            insert_position = index
            if pol.start < old_pol.start:
                found_position = True
                break
        if found_position is False:
            # Check to see if we're actually just adding to the end of the list
            insert_position += 1
        self.polymerases.insert(insert_position, pol)
        self.prop_list.insert(insert_position, pol.speed)

    def _choose_polymerase(self):
        """
        Randomly select next polymerase to move, weighted by move propensity
        (i.e. speed)

        :returns: selected polymerase
        """
        if len(self.prop_list) == 0:
            raise RuntimeError("There are no active polymerases on"
                               "polymer '{0}'.".format(self.name))
        # Randomly select next polymerase to move, weighted by propensity
        pol = weighted_choice(self.polymerases, weights=self.prop_list)
        return pol

    def _move_polymerase(self, pol):
        """
        Move polymerase and deal with collisions and covering/uncovering of
        elements.

        This method is optimized to take advantage of the fact that we only ever
        need to look at the elements that this polymerase is covering, and then
        one element ahead on the polymer, and one element behind after the
        polymerase has moved.

        :param pol: polymerase to move
        """

        if pol not in self.polymerases:
            raise RuntimeError("Attempting to move unbound polymerase '{0}' "
                               "on polymer '{1}'".format(pol.name, self.name))

        # Find which elements this polymerase is covering and
        # temporarily uncover them
        save_index = pol.left_most_element
        while self.elements[save_index].start <= pol.stop:
            if self.elements_intersect(pol, self.elements[save_index]):
                self.elements[save_index].save_state()
                self.elements[save_index].uncover()
            save_index += 1
            if save_index >= len(self.elements):
                break

        # Move polymerase
        pol.move()

        # First resolve any collisions between polymerases
        pol_collision = self._resolve_collisions(pol)
        mask_collision = self._resolve_mask_collisions(pol)
        # If no collisions occurred, it's safe to broadcast that polymerase
        # has moved
        if not pol_collision and not mask_collision:
            pol.move_signal.fire()

        # Check for uncoverings
        old_index = pol.left_most_element
        reset_index = True
        while self.elements[old_index].start <= pol.stop:
            if self.elements_intersect(pol, self.elements[old_index]):
                if reset_index is True:
                    pol.left_most_element = old_index
                    reset_index = False
                self.elements[old_index].cover()
                self._resolve_termination(pol, self.elements[old_index])
            self.elements[old_index].check_state()
            self.elements[old_index].save_state()
            old_index += 1
            if old_index >= len(self.elements):
                break
        # Check to see if the polymerase has run off the end of the polymer
        if pol.stop > self.stop:
            self.terminate(pol, self.stop)

    def _resolve_termination(self, pol, element):
        """
        Check to see if this polymerase should terminate when interacting with
        this element.

        :param pol: polymerase object
        :param element: element object
        """
        if element.type != "terminator":
            return
        if not element.check_interaction(pol.name):
            return
        if element.readthrough:
            return
        random_num = random.random()
        if random_num <= element.efficiency[pol.name]["efficiency"]:
            element.uncover()
            self.terminate(pol, element.stop, element.gene)
        else:
            element.readthrough = True

    def _resolve_mask_collisions(self, pol):
        """
        Check for collisions between a polymerase and this polymer's mask.

        :param pol: polymerase object

        :returns: True if the polymerase collides with the mask and shifts the
            mask backwards
        """
        if self.mask.start > self.stop:
            # Is there still a mask?
            return False
        if self.elements_intersect(pol, self.mask):
            if pol.stop - self.mask.start > 1:
                raise RuntimeError("Polymerase '{0}' is overlapping polymer "
                                   "mask by more than one position on polymer"
                                   " '{1}'.".format(pol.name, self.name))
            if self.mask.check_interaction(pol.name):
                self.shift_mask()
            else:
                pol.move_back()
                return True
        return False

    def _resolve_collisions(self, pol):
        """
        Resolve collisions between polymerases.

        :param pol: polymerase with which to check for collisions
        :returns: True if there was at least 1 collision, False otherwise
        """
        collision = False
        index = self.polymerases.index(pol)
        # We only need to check the polymerase ahead of this polymerase
        if index + 1 > len(self.polymerases) - 1:
            return collision
        if self.elements_intersect(pol,
                                   self.polymerases[index + 1]):
            if pol.stop - self.polymerases[index + 1].start > 1:
                raise RuntimeError("Polymerase '{}' (start: {}, stop: {}, "
                                   "index: {}) is overlapping polymerase '{}' "
                                   "(start: {}, stop: {}, index: {}) by more "
                                   "than one position on the polymer '{}'."
                                   .format(
                                        pol.name,
                                        pol.start,
                                        pol.stop,
                                        index,
                                        self.polymerases[index + 1].name,
                                        self.polymerases[index + 1].start,
                                        self.polymerases[index + 1].stop,
                                        index + 1,
                                        self.name
                                        )
                                   )
            pol.move_back()
            collision = True
        return collision

    def elements_intersect(self, element1, element2):
        """
        Do two line segments (e.g. `Polymerase` objects) overlap?

        :param element1: first element
        :param element2: second element
        :returns: True if elements intersect
        """
        return element1.stop >= element2.start and \
            element2.stop >= element1.start

    def __str__(self):
        """
        Convert `Polymer` object to string representation showing features and
        polymerases.
        """
        out_string = "\n" + self.name + ":\n"
        feature_locs = ["o"]*(self.length + 1)
        for i in range(self.mask.start, self.mask.stop + 1):
            feature_locs[i] = "x"
        for index, feature in enumerate(self.polymerases):
            for i in range(feature.start, feature.stop + 1):
                feature_locs[i] = "P" + str(index)
        for feature in self.elements:
            for i in range(feature.start, feature.stop + 1):
                feature_locs[i] = feature._covered
        for pol in self.polymerases:
            out_string += pol.name + " " + str(pol.start) + "," + str(pol.stop) + " " + \
                str(pol.left_most_element) + "\n"
        out_string += "mask " + str(self.mask.start) + "," + str(self.mask.stop) + "\n"
        out_string += "\n" + ''.join(map(str, feature_locs)) + "\n"
        return out_string


class Genome(Polymer):
    """
    Track polymerases on DNA, deal with collisions, promoters, terminators, and
    constructing transcripts. Inherits from Polymer. Unlike Polymer, Genome
    must construct a transcript upon promoter binding.
    """
    def __init__(self, name, length, elements, transcript_template, mask):
        """
        :param name: name of this genome
        :param length: length of genome (do we still need this?)
        :param elements: DNA elements (promoters, terminators)
        :param transcript_template: list of parameters for all possible
            transcripts produced by this genome (i.e. the largest possible
            polycistronic transcript)
        :param mask: polymer mask (i.e. portion of genome that has not yet
            entered the cell and remains inaccessible)
        """
        super().__init__(name, 1, length, elements, mask)
        self.transcript_template = transcript_template
        self.transcript_signal = Signal()  # fires upon transcript construction

    def bind_polymerase(self, pol, promoter):
        """
        Bind a polymerase to genome and construct new transcript.

        :param pol: polymerase to bind
        :param promoter: name of promoter to which this polymerase binds
        """
        # Bind polymerase just like in parent Polymer
        super().bind_polymerase(pol, promoter)
        # Construct transcript
        transcript = self._build_transcript(pol.start, self.stop)
        # Connect polymerase movement signal to transcript, so that the
        # transcript knows when to expose new elements
        pol.move_signal.connect(transcript.shift_mask)
        pol.release_signal.connect(transcript.release)
        # Fire new transcript signal
        self.transcript_signal.fire(transcript)

    def terminate(self, pol, element_stop, element_gene=""):
        self.prop_sum -= pol.speed
        pol.release_signal.fire(element_stop)
        index = self.polymerases.index(pol)
        self.termination_signal.fire(pol.name)
        self.propensity_signal.fire()
        del self.polymerases[index]
        del self.prop_list[index]

    def _build_transcript(self, start, stop):
        """
        Build a transcript object corresponding to start and stop positions
        within this genome.

        TODO: Find less janky way of constructing a transcript

        :param start: start position of transcript within genome
        :param stop: stop position of transcript within genome
        :returns: polymer object, list of species that need to be added to
            species-level pool
        """
        assert start >= 0
        assert stop > 0
        elements = []
        for element in self.transcript_template:
            if element["start"] >= start and element["stop"] <= stop:
                # Is this element within the start and stop sites?
                rbs = Promoter("rbs",
                               element["start"]+element["rbs"],
                               element["start"],
                               ["ribosome"])
                stop_site = Terminator("tstop",
                                       element["stop"]-1,
                                       element["stop"],
                                       {"ribosome": {"efficiency": 1.0}})
                stop_site.gene = element["name"]
                elements.append(rbs)
                elements.append(stop_site)
        if len(elements) == 0:
            raise RuntimeError("Attempting to create a transcript with no "
                               "elements from genome '{0}'.".format(self.name))
        # build transcript
        polymer = Transcript("rna",
                             self.start,
                             self.stop,
                             elements,
                             Mask("mask", start, stop,
                                  []))
        return polymer


class Transcript(Polymer):
    """
    An mRNA transcript. Tracks ribosomes and protein production. Only differs
    from Polymer in capability to receive signals from a moving polymerase and
    uncover the appropriate, "newly-synthesized" elements.
    """
    def __init__(self, name, start, stop, elements, mask):
        super().__init__(name, start, stop, elements, mask)

    def terminate(self, pol, element_stop, element_gene=""):
        self.prop_sum -= pol.speed
        pol.release_signal.fire(element_stop)
        index = self.polymerases.index(pol)
        self.termination_signal.fire(pol.name, element_gene)
        self.propensity_signal.fire()
        del self.polymerases[index]
        del self.prop_list[index]

    def release(self, stop):
        """
        Roll back mask to a given stop point.

        FIX: Where do we check for newly-revealed elements?

        :param stop: stop site in genomic coordinates
        """
        jump = stop - self.mask.start
        self.mask.start += jump
