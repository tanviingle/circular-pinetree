#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "choices.hpp"
#include "feature.hpp"
#include "polymer.hpp"
#include "simulation.hpp"
#include "tracker.hpp"

namespace py = pybind11;
using namespace pybind11::literals;

PYBIND11_MODULE(pinetree, m) {
  m.doc() = (R"doc(
    Python module
    -----------------------
    .. currentmodule:: pysinthe.core
  )doc");

  m.def("seed", &Random::seed, "Set a global seed for the simulation.");

  py::class_<SpeciesTracker>(m, "SpeciesTracker")
      .def("get_instance", SpeciesTracker::Instance,
           py::return_value_policy::reference)
      .def("increment", &SpeciesTracker::Increment);

  py::class_<Simulation, std::shared_ptr<Simulation>>(
      m, "Simulation", "Set up and run a gene expression simulation.")
      .def(py::init<int, int, double>(), "run_time"_a, "time_step"_a,
           "cell_volume"_a)
      .def_property("stop_time",
                    (double (Simulation::*)()) & Simulation::stop_time,
                    (void (Simulation::*)(double)) & Simulation::stop_time,
                    "stop time of simulation")
      .def_property("time_step",
                    (double (Simulation::*)()) & Simulation::time_step,
                    (void (Simulation::*)(double)) & Simulation::time_step,
                    "time step at which to output data")
      .def("add_reaction", &Simulation::AddReaction,
           "add a species-level reaction")
      .def("register_genome", &Simulation::RegisterGenome, "register a genome")
      .def("add_species", &Simulation::AddSpecies, "add species")
      .def("add_polymerase", &Simulation::AddPolymerase, "name"_a,
           "footprint"_a, "speed"_a, "copy_number"_a, "add a polymerase")
      .def("run", &Simulation::Run, "run the simulation");

  // Binding for abtract Reaction so pybind11 doesn't complain when doing
  // conversions between Reaction and its child classes
  py::class_<Reaction, Reaction::Ptr>(
      m, "Reaction", "A generic Reaction designed to be extended.");
  py::class_<SpeciesReaction, Reaction, SpeciesReaction::Ptr>(
      m, "SpeciesReaction", "Define a species-level reaction.")
      .def(py::init<double, double, const std::vector<std::string> &,
                    const std::vector<std::string> &>());
  py::class_<Bind, Reaction, std::shared_ptr<Bind>>(m, "Bind").def(
      py::init<double, double, const std::string &, const Polymerase &>());
  py::class_<Bridge, Reaction, std::shared_ptr<Bridge>>(m, "Bridge")
      .def(py::init<Polymer::Ptr>());

  // Features and elements
  py::class_<Feature, std::shared_ptr<Feature>>(m, "Feature")
      .def_property("start", (int (Feature::*)()) & Feature::start,
                    (void (Feature::*)(int)) & Feature::start)
      .def_property("stop", (int (Feature::*)()) & Feature::stop,
                    (void (Feature::*)(int)) & Feature::stop)
      .def_property_readonly(
          "type", (const std::string &(Feature::*)() const) & Feature::type)
      .def_property_readonly(
          "name", (const std::string &(Feature::*)() const) & Feature::name);
  py::class_<Element, Feature, Element::Ptr>(m, "Element")
      .def_property("gene",
                    (const std::string &(Element::*)() const) & Element::gene,
                    (void (Element::*)(const std::string &)) & Element::gene);
  py::class_<Promoter, Element, Promoter::Ptr>(m, "Promoter")
      .def(py::init<const std::string &, int, int,
                    const std::map<std::string, double> &>());
  py::class_<Terminator, Element, Terminator::Ptr>(m, "Terminator")
      .def(py::init<const std::string &, int, int,
                    const std::map<std::string, double> &>())
      .def_property(
          "reading_frame", (int (Terminator::*)()) & Terminator::reading_frame,
          (void (Terminator::*)(int)) & Terminator::set_reading_frame);
  py::class_<Polymerase, Feature, Polymerase::Ptr>(m, "Polymerase")
      .def(py::init<const std::string &, int, int>());

  // Polymers, genomes, and transcripts
  py::class_<Polymer, Polymer::Ptr>(m, "Polymer");
  py::class_<Genome, Polymer, Genome::Ptr>(m, "Genome")
      .def(py::init<const std::string &, int>(), "name"_a, "length"_a)
      .def("add_mask", &Genome::AddMask, "start"_a, "interactions"_a)
      .def("add_weights", &Genome::AddWeights, "weights"_a)
      .def("add_promoter", &Genome::AddPromoter, "name"_a, "start"_a, "stop"_a,
           "interactions"_a)
      .def("add_terminator", &Genome::AddTerminator, "name"_a, "start"_a,
           "stop"_a, "efficiency"_a)
      .def("add_gene", &Genome::AddGene, "name"_a, "start"_a, "stop"_a,
           "rbs_start"_a, "rbs_stop"_a, "rbs_strength"_a);
}