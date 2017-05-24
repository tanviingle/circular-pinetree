/* Copyright (c) 2017 Benjamin Jack All Rights Reserved. */

#ifndef SRC_TRACKER_HPP // header guard
#define SRC_TRACKER_HPP

#include <memory>

#include "simulation.hpp"

/**
 * Tracks species' copy numbers and maintains promoter-to-polymer and species-
 * to-reaction maps to easily look up which polymers contain a given promoter
 * and which reactions involve a given species. These maps are needed to cache
 * propensities and increase the performance of the simulation.
 *
 * Follows a singleton pattern:
 * http://stackoverflow.com/a/1008289/5360633
 *
 * TODO: Move propensity cache from Simulation into this class?
 */
class SpeciesTracker {
public:
  /**
   * Retrieve the only instance of this object.
   */
  static SpeciesTracker &Instance();
  /**
   * Clear all data in the tracker.
   */
  void Clear();
  /**
   * Delete copy constructor and assignment operator.
   */
  SpeciesTracker(SpeciesTracker const &) = delete;
  void operator=(SpeciesTracker const &) = delete;
  /**
   * Register a SpeciesReaction with the species tracker.
   */
  void Register(SpeciesReaction::Ptr reaction);
  /**
   * Change a species count by a given value (positive or negative).
   *
   * @param species_name name of species to change count
   * @param copy_number number to add to current copy number count
   */
  void Increment(const std::string &species_name, int copy_number);
  /**
   * Update ribosome count for a given transcript.
   *
   * @param transcript_name name of transcript (usually a gene)
   * @param copy_number number to add to current copy number count
   */
  void IncrementRibo(const std::string &transcript_name, int copy_number);
  /**
   * Add a species-reaction pair to species-reaction map.
   *
   * @param species_name name of species
   * @param reaction reaction object (pointer) that involves species
   */
  void Add(const std::string &species_name, Reaction::Ptr reaction);
  /**
   * Add a promoter-polymer pair to promoter-polymer map.
   *
   * @param promter_name of promoter
   * @param polymer polymer object that contains the named promoter (pointer)
   */
  void Add(const std::string &promoter_name, Polymer::Ptr polymer);
  /**
   * Get polymers that contain a given promoter.
   *
   * @param promoter_name name of promoter
   *
   * @return vector of pointers to Polymer objects that contain promoter_name
   */
  const Polymer::VecPtr &FindPolymers(const std::string &promoter_name);
  /**
   * Get reactions that involve a given species.
   *
   * @param species_name name of species
   *
   * @return vector of pointers to Reaction objects that involve species_name
   */
  const Reaction::VecPtr &FindReactions(const std::string &species_name);
  /**
   * Getters and setters
   */
  int species(const std::string &reactant);
  const std::map<std::string, int> &species() { return species_; }
  const std::map<std::string, int> &ribo_per_transcript() {
    return ribo_per_transcript_;
  }
  /**
   * Signal to fire when propensity needs to be updated.
   */
  Signal<int> propensity_signal_;

private:
  /**
   * Private constructor for singleton
   */
  SpeciesTracker() {}
  /**
   * Species counts.
   */
  std::map<std::string, int> species_;
  /**
   * Transcript (gene) counts.
   */
  std::map<std::string, int> transcripts_;
  /**
   * Number of ribosomes on each transcript (gene).
   */
  std::map<std::string, int> ribo_per_transcript_;
  /**
   * Promoter-to-polymer map.
   */
  std::map<std::string, Polymer::VecPtr> promoter_map_;
  /**
   * Species-to-reaction map.
   */
  std::map<std::string, Reaction::VecPtr> species_map_;
};

#endif // header guard