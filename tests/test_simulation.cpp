#include <catch.hpp>

#include "simulation.hpp"
#include "tracker.hpp"

TEST_CASE("SpeciesReaction methods", "[Reaction]") {
  auto reaction = std::make_shared<SpeciesReaction>(
      1000, double(8e-15), std::vector<std::string>{"reactant1", "reactant2"},
      std::vector<std::string>{"product1", "product2"});
  auto &tracker = SpeciesTracker::Instance();
  tracker.Clear();
  tracker.Register(reaction);
  tracker.Increment("reactant1", 2);
  tracker.Increment("reactant2", 3);

  SECTION("Initialization and registration") {
    REQUIRE_THROWS(SpeciesReaction(
        1000, double(8e-15),
        std::vector<std::string>{"reactant1", "reactant2", "reactant3"},
        std::vector<std::string>{"product1", "product2"}));
    // Make sure that maps have been set up appropriately
    auto reactions = tracker.FindReactions("reactant1");
    REQUIRE(std::find(reactions.begin(), reactions.end(), reaction) !=
            reactions.end());
    reactions = tracker.FindReactions("reactant2");
    REQUIRE(std::find(reactions.begin(), reactions.end(), reaction) !=
            reactions.end());
    reactions = tracker.FindReactions("product1");
    REQUIRE(std::find(reactions.begin(), reactions.end(), reaction) !=
            reactions.end());
    reactions = tracker.FindReactions("product2");
    REQUIRE(std::find(reactions.begin(), reactions.end(), reaction) !=
            reactions.end());
  }

  SECTION("Propensity calculation") {
    REQUIRE((1000 * 2 * 3) / (double(6.0221409e+23) * double(8e-15)) ==
            reaction->CalculatePropensity());
  }

  SECTION("Execution") {
    reaction->Execute();
    REQUIRE(tracker.species("reactant1") == 1);
    REQUIRE(tracker.species("reactant2") == 2);
    REQUIRE(tracker.species("product1") == 1);
    REQUIRE(tracker.species("product1") == 1);
  }
}

TEST_CASE("Bind methods", "[Reaction]") {
  auto &tracker = SpeciesTracker::Instance();
  tracker.Clear();
  // Set up a polymer
  std::map<std::string, double> interactions{
      {"ecolipol", 1.0},
  };
  Promoter::Ptr prom;
  Terminator::Ptr term;
  prom = std::make_shared<Promoter>("p1", 5, 15, interactions);
  std::map<std::string, double> efficiency;
  efficiency["ecolipol"] = 0.6;
  term = std::make_shared<Terminator>("t1", 50, 55, efficiency);

  std::vector<Element::Ptr> elements;
  elements.push_back(prom);
  elements.push_back(term);
  std::map<std::string, double> mask_interactions{
      {"ecolipol", 1.0},
  };
  Mask mask = Mask("test_mask", 50, 100, mask_interactions);

  auto polymer =
      std::make_shared<Polymer>("test_polymer", 1, 100, elements, mask);
  polymer->InitElements();
  // Set up a polymerase
  auto polymerase = Polymerase("ecolipol", 10, 30);
  auto reaction = Bind(1000, double(8e-15), "p1", polymerase);

  SECTION("Calculate propensity") {
    tracker.Increment("p1", 2);
    tracker.Increment("ecolipol", 3);
    REQUIRE((1000 * 3 * 3) / (double(6.0221409e+23) * double(8e-15)) ==
            reaction.CalculatePropensity());
  }

  SECTION("Execution") {
    tracker.Clear();
    tracker.Increment("p1", 1);
    tracker.Increment("ecolipol", 1);
    tracker.Add("p1", polymer);
    reaction.Execute();
    REQUIRE(tracker.species("p1") == 0);
    REQUIRE(tracker.species("ecolipol") == 0);
    REQUIRE(polymer->uncovered("p1") == 0);
    REQUIRE(prom->IsCovered());
  }
}

TEST_CASE("SpeciesTracker methods", "[SpeciesTracker]") {
  auto &tracker = SpeciesTracker::Instance();
  tracker.Clear();

  SECTION("Increment species") {
    tracker.Increment("reactant1", 1);
    REQUIRE(tracker.species("reactant1") == 1);
    tracker.Increment("reactant2", 1);
    REQUIRE(tracker.species("reactant2") == 1);
    tracker.Increment("reactant1", 2);
    REQUIRE(tracker.species("reactant1") == 3);
  }

  SECTION("Add polymer") {
    Polymer::Ptr polymer;
    tracker.Add("promoter1", polymer);
    auto polymers = tracker.FindPolymers("promoter1");
    REQUIRE(std::find(polymers.begin(), polymers.end(), polymer) !=
            polymers.end());
    tracker.Add("promoter2", polymer);
    polymers = tracker.FindPolymers("promoter2");
    REQUIRE(std::find(polymers.begin(), polymers.end(), polymer) !=
            polymers.end());
  }
}

TEST_CASE("Simulation methods", "[Simulation]") {
  auto sim = std::make_shared<Simulation>(10, 1, double(8e-15));
  auto &tracker = SpeciesTracker::Instance();
  tracker.Clear();
  tracker.Increment("reactant1", 1);

  SECTION("Register reaction") {
    sim->AddReaction(1.5, std::vector<std::string>{"reactant1"},
                     std::vector<std::string>{"product1"});
    sim->InitPropensity();
    REQUIRE(sim->alpha_sum() == 1.5);
    sim->AddReaction(1.5, std::vector<std::string>{"reactant1"},
                     std::vector<std::string>{"product1"});
    sim->InitPropensity();
    REQUIRE(sim->alpha_sum() == 3);
  }

  SECTION("Register polymer and execute") {
    tracker.Clear();
    // Set up a genome
    auto genome = std::make_shared<Genome>("test_polymer", 100);
    std::map<std::string, double> interactions{
        {"ecolipol", 1000},
    };
    genome->AddPromoter("p1", 5, 15, interactions);
    std::map<std::string, double> efficiency;
    efficiency["ecolipol"] = 0.6;
    genome->AddTerminator("t1", 50, 55, efficiency);

    std::vector<std::string> mask_interactions{"ecolipol"};
    genome->AddMask(50, mask_interactions);

    sim->RegisterGenome(genome);
    REQUIRE(tracker.FindPolymers("p1")[0] == genome);
    // Add a polymerase
    sim->AddPolymerase("ecolipol", 10, 30, 2);

    sim->InitPropensity();
    tracker.propensity_signal_.ConnectMember(sim,
                                             &Simulation::UpdatePropensity);
    sim->Execute();
    REQUIRE(sim->alpha_sum() == 30);
    sim->Execute();
    REQUIRE(sim->alpha_sum() == 30);
    for (int i = 0; i < 20; i++) {
      sim->Execute();
    }
    // Alpha_sum should be slightly greather than 30 now that promoter is
    // re-exposed
    REQUIRE(sim->alpha_sum() > 30);
  }
}